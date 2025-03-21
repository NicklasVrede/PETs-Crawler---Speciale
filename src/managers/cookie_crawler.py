import time
import re
import os
import sys
import atexit
from typing import Dict, List, Optional, Any
from tqdm import tqdm
from playwright.sync_api import sync_playwright, Page, Browser

# Fix imports with relative paths
try:
    from managers.cookie_database import CookieDatabase
except ImportError:
    try:
        from cookie_database import CookieDatabase
    except ImportError:
        # Try alternative import paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(os.path.dirname(current_dir))
        sys.path.append(parent_dir)
        from src.managers.cookie_database import CookieDatabase

class CookieCrawler:
    """
    Manages the crawling of cookiesearch.org to retrieve cookie information.
    Uses Playwright for browser automation and stores results in CookieDatabase.
    """
    
    def __init__(self, database=None, headless=False, slow_mo=50):
        """
        Initialize the cookie crawler with a browser instance.
        
        Args:
            database: CookieDatabase instance to use (creates a new one if None)
            headless: Whether to run the browser in headless mode
            slow_mo: Slow down browser interactions by this amount (ms)
        """
        self.database = database or CookieDatabase()
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser = None
        self.page = None
        self._init_browser()
        
        # Register cleanup at exit
        atexit.register(self.close)
        
    def _init_browser(self):
        """Initialize the browser instance and page"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            self.page = self.browser.new_page()
            tqdm.write("Browser session initialized.")
        except Exception as e:
            tqdm.write(f"Error initializing browser: {str(e)}")
            self.close()
            raise
            
    def close(self):
        """Clean up browser resources"""
        if self.page:
            try:
                self.page.close()
            except:
                pass
            self.page = None
            
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
            self.browser = None
            
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
            self.playwright = None
            
        tqdm.write("Browser session closed.")
    
    def lookup_cookies_batch(self, cookie_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Look up multiple cookies using the persistent browser session and page.
        
        Args:
            cookie_names: List of cookie names to look up
            
        Returns:
            Dictionary mapping cookie names to their information
        """
        results = {}
        
        # Only show progress bar if we have multiple cookies
        if len(cookie_names) > 1:
            iterator = tqdm(cookie_names, desc="Looking up cookies")
        else:
            iterator = cookie_names
            
        for name in iterator:
            # Skip if already in database and classified as unknown
            if (self.database.contains(name) and 
                    self.database.get(name).get('category', '').lower() == 'unknown'):
                tqdm.write(f"Skipping previously classified unknown cookie: {name}")
                results[name] = self.database.get(name)
                continue
                
            try:
                info = self.lookup_cookie(name)
                results[name] = info
                self.database.add(name, info)
                # Only save after each lookup if we're doing single lookups
                if len(cookie_names) == 1:
                    self.database.save()
            except Exception as e:
                tqdm.write(f"Error processing {name}: {str(e)}")
                results[name] = self.database.create_unknown_cookie(name)
        
        # Save once at the end if we processed multiple cookies
        if len(cookie_names) > 1:
            self.database.save()
        
        return results
    
    def lookup_cookie(self, name: str) -> Dict[str, Any]:
        """
        Look up a single cookie using the persistent page.
        
        Args:
            name: Name of the cookie to look up
            
        Returns:
            Dictionary with cookie information
        """
        try:
            # Check if cookie exists in database already
            if self.database.contains(name):
                return self.database.get(name)
                
            # Always try direct lookup first
            url = f"https://cookiesearch.org/cookies/?search-term={name}&filter-type=cookie-name&sort=asc&cookie-id={name}"
            tqdm.write(f"Looking up cookie: {name}")
            
            # Use domcontentloaded for faster page loading
            self.page.goto(url, wait_until='domcontentloaded')
            
            # Check if we're on a details page and have a valid ID
            on_details_page = self.page.locator('text=Cookie ID').count() > 0
            if on_details_page:
                cookie_id = self._get_field_value('Cookie ID')
                if cookie_id != "Not specified":
                    # Direct lookup succeeded
                    tqdm.write(f"Direct lookup successful for: {name}")
                    info = {
                        'name': name,
                        'cookie_id': cookie_id,
                        'category': self._get_field_value('Category'),
                        'script': self._get_field_value('Script'),
                        'description': self._get_field_value('Description'),
                        'url': self.page.url,
                        'script_url': self._get_script_url(),
                        'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'match_type': 'direct'
                    }
                    return info
            
            # If direct lookup failed, try with the simplified name
            tqdm.write(f"Direct lookup failed for: {name}, trying with simplified name")
            
            # Try progressively simplifying the name
            simplified_name = name
            while True:
                # Find the last special character in the current simplified name
                last_special_idx = -1
                for char in ['_', '.', '-']:
                    idx = simplified_name.rfind(char)
                    if idx > last_special_idx:
                        last_special_idx = idx
                
                # If we found a special character, split on it
                if last_special_idx > 0:
                    # Keep everything before the last special character
                    new_simplified_name = simplified_name[:last_special_idx]
                    tqdm.write(f"Simplifying from '{simplified_name}' to '{new_simplified_name}'")
                    simplified_name = new_simplified_name
                    
                    # Try lookup with this simplified name
                    result = self._try_simplified_lookup(name, simplified_name)
                    if result:
                        return result
                else:
                    # No more special characters to split on
                    break
            
            # If all lookups failed, create an unknown cookie entry
            return self.database.create_unknown_cookie(name)
            
        except Exception as e:
            tqdm.write(f"Error looking up cookie {name}: {str(e)}")
            return self.database.create_unknown_cookie(name)
            
    def _try_simplified_lookup(self, original_name: str, simplified_name: str) -> Optional[Dict[str, Any]]:
        """
        Try lookup using a simplified cookie name.
        
        Args:
            original_name: Original cookie name
            simplified_name: Simplified version of the name to try
            
        Returns:
            Cookie information if found, None otherwise
        """
        tqdm.write(f"Trying lookup with: {simplified_name}")
        
        # First try direct lookup
        simple_url = f"https://cookiesearch.org/cookies/?search-term={simplified_name}&filter-type=cookie-name&sort=asc&cookie-id={simplified_name}"
        self.page.goto(simple_url, wait_until='domcontentloaded')
        
        # Check if we're on a details page with a valid ID
        on_details_page = self.page.locator('text=Cookie ID').count() > 0
        if on_details_page:
            cookie_id = self._get_field_value('Cookie ID')
            if cookie_id != "Not specified":
                # Simplified name lookup succeeded
                tqdm.write(f"Simplified name direct lookup successful for: {simplified_name}")
                info = {
                    'name': original_name,
                    'cookie_id': cookie_id,
                    'category': self._get_field_value('Category'),
                    'script': self._get_field_value('Script'),
                    'description': self._get_field_value('Description'),
                    'url': self.page.url,
                    'script_url': self._get_script_url(),
                    'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'match_type': 'simplified'
                }
                return info
        
        # If direct lookup failed, try searching
        tqdm.write(f"Direct lookup failed for simplified name, trying search: {simplified_name}")
        search_url = f"https://cookiesearch.org/cookies/?search-term={simplified_name}&filter-type=cookie-name&sort=asc"
        self.page.goto(search_url, wait_until='domcontentloaded')
        
        # Check if any results found
        no_results = self.page.locator('text=No results found').count() > 0
        if no_results:
            tqdm.write(f"No search results found for simplified name: {simplified_name}")
            return None
        
        # Process search results
        cookie_links = self.page.locator('.result-single')
        results_count = cookie_links.count()
        tqdm.write(f"Found {results_count} search results for {simplified_name}")
        
        # Look for exact match in the results
        result = self._process_search_results(cookie_links, results_count, original_name, simplified_name)
        return result
    
    def _process_search_results(self, cookie_links, results_count, original_name, search_term):
        """Process search results looking for matches"""
        # Look for exact match in the results
        for i in range(results_count):
            try:
                cookie_text = cookie_links.nth(i).locator('.cookie-name').inner_text()
                tqdm.write(f"Result {i+1}: {cookie_text}")
                
                if cookie_text == search_term:
                    tqdm.write(f"Found exact match in search results: {cookie_text}")
                    cookie_links.nth(i).click()
                    self.page.wait_for_load_state('domcontentloaded')
                    
                    # Check if we got to a details page
                    if self.page.locator('text=Cookie ID').count() > 0:
                        cookie_id = self._get_field_value('Cookie ID')
                        if cookie_id != "Not specified":
                            # Match successful
                            info = {
                                'name': original_name,
                                'cookie_id': cookie_id,
                                'category': self._get_field_value('Category'),
                                'script': self._get_field_value('Script'),
                                'description': self._get_field_value('Description'),
                                'url': self.page.url,
                                'script_url': self._get_script_url(),
                                'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'match_type': 'search'
                            }
                            return info
                    return None
            except Exception as e:
                tqdm.write(f"Error processing search result {i+1}: {str(e)}")
        
        # If no exact match, try the first result that starts with our search term
        for i in range(results_count):
            try:
                cookie_text = cookie_links.nth(i).locator('.cookie-name').inner_text()
                if cookie_text.startswith(search_term):
                    tqdm.write(f"Found partial match in search results: {cookie_text}")
                    cookie_links.nth(i).click()
                    self.page.wait_for_load_state('domcontentloaded')
                    
                    # Check if we got to a details page
                    if self.page.locator('text=Cookie ID').count() > 0:
                        cookie_id = self._get_field_value('Cookie ID')
                        if cookie_id != "Not specified":
                            # Match successful
                            info = {
                                'name': original_name,
                                'cookie_id': cookie_id,
                                'category': self._get_field_value('Category'),
                                'script': self._get_field_value('Script'),
                                'description': self._get_field_value('Description'),
                                'url': self.page.url,
                                'script_url': self._get_script_url(),
                                'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'match_type': 'partial'
                            }
                            return info
                    return None
            except Exception as e:
                tqdm.write(f"Error processing partial match {i+1}: {str(e)}")
        
        # No match found
        return None
    
    def _get_field_value(self, label: str) -> str:
        """Helper method to extract field values from the page"""
        try:
            elements = self.page.locator(f'text={label}').all()
            for elem in elements:
                parent_text = elem.locator('..').inner_text()
                if ':' in parent_text:
                    value = parent_text.split(':', 1)[1].strip()
                    return value if value else "Not specified"
            return "Not specified"
        except:
            return "Not specified"
    
    def _get_script_url(self) -> str:
        """Helper method to extract script URL"""
        try:
            elements = self.page.locator('text=URL').all()
            for elem in elements:
                parent_text = elem.locator('..').inner_text()
                if ':' in parent_text:
                    value = parent_text.split(':', 1)[1].strip()
                    if 'cookiesearch.org' not in value:  # Make sure we're not getting the cookiesearch URL
                        return value
            return "Not specified"
        except:
            return "Not specified"
    
    @staticmethod
    def extract_base_name(name: str) -> str:
        """
        Extract the base name from a cookie using pattern recognition.
        
        Args:
            name: Cookie name
            
        Returns:
            Base name or empty string if no pattern recognized
        """
        # Pattern 1: prefix followed by separator and numbers
        # Examples: xyz_123456, abc.12345, etc.
        match = re.match(r'^([a-zA-Z_\-]+)[._\-][\d]+', name)
        if match:
            return match.group(1)
        
        # Pattern 2: parts with separators where the second part has digits
        # Examples: abc_123_xyz, abc_xyz_123
        if '_' in name:
            parts = name.split('_')
            # If second part has digits but first doesn't, return first part
            if len(parts) > 1 and any(c.isdigit() for c in parts[1]) and not any(c.isdigit() for c in parts[0]):
                return parts[0]
            
            # If third part has digits but first and second don't, return first_second
            if (len(parts) > 2 and any(c.isdigit() for c in parts[2]) 
                    and not any(c.isdigit() for c in parts[0]) 
                    and not any(c.isdigit() for c in parts[1])):
                return f"{parts[0]}_{parts[1]}"
        
        # Pattern 3: letters followed by digits (no separator)
        # Example: abc123
        match = re.match(r'^([a-zA-Z_\-]+)[\d]+', name)
        if match:
            return match.group(1)
        
        # No recognizable pattern
        return ""


# Example usage
if __name__ == "__main__":
    # Create a crawler instance
    crawler = CookieCrawler()
    
    try:
        # Example: Look up some common cookies
        cookies_to_lookup = ['_ga', '_fbp', 'session-id', 'PHPSESSID']
        results = crawler.lookup_cookies_batch(cookies_to_lookup)
        
        # Print results
        for name, info in results.items():
            print(f"\nCookie: {name}")
            print(f"Category: {info.get('category', 'Unknown')}")
            print(f"Script: {info.get('script', 'Not specified')}")
            print(f"Match type: {info.get('match_type', 'none')}")
    finally:
        # Ensure browser is closed
        crawler.close()