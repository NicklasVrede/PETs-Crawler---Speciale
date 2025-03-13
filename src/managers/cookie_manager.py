import json
import os
from typing import Dict, Optional, List
from tqdm import tqdm
import time
from playwright.sync_api import sync_playwright
import re

COOKIE_DB_FILE = 'data/cookie_database.json'
cookie_db = {}

def load_cookie_database():
    """Load our local cookie database"""
    global cookie_db
    try:
        if os.path.exists(COOKIE_DB_FILE):
            with open(COOKIE_DB_FILE, 'r') as f:
                cookie_db.update(json.load(f))
                tqdm.write(f"Loaded {len(cookie_db)} cookie definitions")
    except Exception as e:
        tqdm.write(f"Error loading cookie database: {e}")

def save_cookie_database():
    """Save our cookie database to file"""
    try:
        if cookie_db:
            os.makedirs(os.path.dirname(COOKIE_DB_FILE), exist_ok=True)
            with open(COOKIE_DB_FILE, 'w') as f:
                json.dump(cookie_db, f, indent=2)
            tqdm.write(f"Saved {len(cookie_db)} cookie definitions")
    except Exception as e:
        tqdm.write(f"Error saving cookie database: {e}")

def lookup_cookie(name: str) -> Optional[Dict]:
    """Look up cookie information from cookiesearch.org using Playwright"""
    
    # Check if this cookie has already been looked up and classified as unknown
    if name in cookie_db and cookie_db[name].get('category') == 'unknown':
        tqdm.write(f"Skipping previously classified unknown cookie: {name}")
        return cookie_db[name]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()
        
        try:
            # Always try direct lookup first
            url = f"https://cookiesearch.org/cookies/?search-term={name}&filter-type=cookie-name&sort=asc&cookie-id={name}"
            tqdm.write(f"Looking up cookie: {name}")
            page.goto(url)
            time.sleep(2)
            
            # Helper function for extracting field values
            def get_field_value(label: str) -> str:
                try:
                    elements = page.locator(f'text={label}').all()
                    for elem in elements:
                        parent_text = elem.locator('..').inner_text()
                        if ':' in parent_text:
                            value = parent_text.split(':', 1)[1].strip()
                            return value if value else "Not specified"
                    return "Not specified"
                except:
                    return "Not specified"
            
            # Check if we're on a details page and have a valid ID
            on_details_page = page.locator('text=Cookie ID').count() > 0
            if on_details_page:
                cookie_id = get_field_value('Cookie ID')
                if cookie_id != "Not specified":
                    # Direct lookup succeeded
                    tqdm.write(f"Direct lookup successful for: {name}")
                    info = {
                        'name': name,
                        'cookie_id': cookie_id,
                        'category': get_field_value('Category'),
                        'script': get_field_value('Script'),
                        'description': get_field_value('Description'),
                        'url': page.url,
                        'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'match_type': 'direct'
                    }
                    browser.close()
                    cookie_db[name] = info
                    return info
            
            # If direct lookup failed, try with the simplified name
            tqdm.write(f"Direct lookup failed for: {name}, trying with simplified name")
            
            # Try progressively simplifying the name, starting from the last special character
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
                    tqdm.write(f"Trying lookup with: {simplified_name}")
                    
                    # First try direct lookup
                    simple_url = f"https://cookiesearch.org/cookies/?search-term={simplified_name}&filter-type=cookie-name&sort=asc&cookie-id={simplified_name}"
                    page.goto(simple_url)
                    time.sleep(2)
                    
                    # Check if we're on a details page with a valid ID
                    on_details_page = page.locator('text=Cookie ID').count() > 0
                    if on_details_page:
                        cookie_id = get_field_value('Cookie ID')
                        if cookie_id != "Not specified":
                            # Simplified name lookup succeeded
                            tqdm.write(f"Simplified name direct lookup successful for: {simplified_name}")
                            info = {
                                'name': name,
                                'cookie_id': cookie_id,
                                'category': get_field_value('Category'),
                                'script': get_field_value('Script'),
                                'description': get_field_value('Description'),
                                'url': page.url,
                                'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'match_type': 'simplified'
                            }
                            browser.close()
                            cookie_db[name] = info
                            return info
                    
                    # If direct lookup failed, try searching
                    tqdm.write(f"Direct lookup failed for simplified name, trying search: {simplified_name}")
                    search_url = f"https://cookiesearch.org/cookies/?search-term={simplified_name}&filter-type=cookie-name&sort=asc"
                    page.goto(search_url)
                    time.sleep(2)
                    
                    # Check if any results found
                    no_results = page.locator('text=No results found').count() > 0
                    if no_results:
                        tqdm.write(f"No search results found for simplified name: {simplified_name}")
                        continue
                    
                    # Process search results
                    cookie_links = page.locator('.result-single')
                    results_count = cookie_links.count()
                    tqdm.write(f"Found {results_count} search results for {simplified_name}")
                    
                    # Look for exact match in the results
                    exact_match_found = False
                    for i in range(results_count):
                        try:
                            cookie_text = cookie_links.nth(i).locator('.cookie-name').inner_text()
                            tqdm.write(f"Result {i+1}: {cookie_text}")
                            
                            if cookie_text == simplified_name:
                                tqdm.write(f"Found exact match in search results: {cookie_text}")
                                cookie_links.nth(i).click()
                                time.sleep(2)
                                
                                # Check if we got to a details page
                                if page.locator('text=Cookie ID').count() > 0:
                                    cookie_id = get_field_value('Cookie ID')
                                    if cookie_id != "Not specified":
                                        # Match successful
                                        info = {
                                            'name': name,
                                            'cookie_id': cookie_id,
                                            'category': get_field_value('Category'),
                                            'script': get_field_value('Script'),
                                            'description': get_field_value('Description'),
                                            'url': page.url,
                                            'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                            'match_type': 'search'
                                        }
                                        browser.close()
                                        cookie_db[name] = info
                                        return info
                                exact_match_found = True
                                break
                        except Exception as e:
                            tqdm.write(f"Error processing search result {i+1}: {str(e)}")
                    
                    # If we found and processed an exact match, but didn't return, move to the next iteration
                    if exact_match_found:
                        continue
                    
                    # If no exact match, try the first result that starts with our simplified name
                    for i in range(results_count):
                        try:
                            cookie_text = cookie_links.nth(i).locator('.cookie-name').inner_text()
                            if cookie_text.startswith(simplified_name):
                                tqdm.write(f"Found partial match in search results: {cookie_text}")
                                cookie_links.nth(i).click()
                                time.sleep(2)
                                
                                # Check if we got to a details page
                                if page.locator('text=Cookie ID').count() > 0:
                                    cookie_id = get_field_value('Cookie ID')
                                    if cookie_id != "Not specified":
                                        # Match successful
                                        info = {
                                            'name': name,
                                            'cookie_id': cookie_id,
                                            'category': get_field_value('Category'),
                                            'script': get_field_value('Script'),
                                            'description': get_field_value('Description'),
                                            'url': page.url,
                                            'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                            'match_type': 'partial'
                                        }
                                        browser.close()
                                        cookie_db[name] = info
                                        return info
                                break
                        except Exception as e:
                            tqdm.write(f"Error processing partial match {i+1}: {str(e)}")
                else:
                    # No more special characters to split on
                    break
            
            # If we get here, all attempts failed
            tqdm.write(f"No match found for: {name}")
            cookie_db[name] = {
                'name': name,
                'cookie_id': 'unknown',
                'category': 'unknown',
                'script': 'unknown', 
                'description': 'No match found',
                'url': '',
                'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'match_type': 'none'
            }
            browser.close()
            return cookie_db[name]
            
        except Exception as e:
            tqdm.write(f"Error looking up cookie {name}: {str(e)}")
            # Store as unknown cookie with error info
            cookie_db[name] = {
                'name': name,
                'cookie_id': 'unknown',
                'category': 'unknown',
                'script': 'unknown',
                'description': f'Lookup error: {str(e)}',
                'url': '',
                'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'match_type': 'none'
            }
            browser.close()
            return cookie_db[name]

def should_attempt_pattern_match(name: str) -> bool:
    """
    Determine if a cookie name has a pattern that warrants pattern matching.
    Only return True for obvious patterns where pattern matching makes sense.
    """
    # Check if it contains an underscore and has digits
    has_underscore = '_' in name
    has_digits = any(c.isdigit() for c in name)
    
    # Only attempt pattern matching if there's both an underscore and digits
    # This targets cookies like _ga_123456 but avoids random named cookies
    return has_underscore and has_digits

def get_conservative_search_term(name: str) -> str:
    """
    Get a conservative search term from a cookie name.
    Only returns the first part before an underscore if it contains digits.
    """
    if '_' in name:
        # Get first part
        first_part = name.split('_')[0]
        # Only if it's not empty
        if first_part:
            return first_part
            
    # Default: no pattern match
    return ""

def analyze_cookie(name: str) -> Optional[Dict]:
    """Analyze a cookie, using local DB first then cookiesearch.org"""
    # Check our local database first
    if name in cookie_db:
        return cookie_db[name]
    
    # Look up on cookiesearch.org
    info = lookup_cookie(name)
    if info:
        # Save to our database
        cookie_db[name] = info
        save_cookie_database()
        return info
    
    return None

def extract_base_name(name: str) -> str:
    """
    Extract the base name from a cookie using pattern recognition.
    """
    # Pattern 1: prefix followed by separator and numbers
    # Examples: xyz_123456, abc.12345, etc.
    # Match pattern: letters/symbols, then separator, then digits
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
        if len(parts) > 2 and any(c.isdigit() for c in parts[2]) and not any(c.isdigit() for c in parts[0]) and not any(c.isdigit() for c in parts[1]):
            return f"{parts[0]}_{parts[1]}"
    
    # Pattern 3: letters followed by digits (no separator)
    # Example: abc123
    match = re.match(r'^([a-zA-Z_\-]+)[\d]+', name)
    if match:
        return match.group(1)
    
    # No recognizable pattern
    return ""

# Load database at module import
load_cookie_database()

# Register save function for exit
import atexit
atexit.register(save_cookie_database)

def test_amazon_cookies():
    """Test function to extract and lookup cookies from Amazon.co.uk.json"""
    import json
    import os
    
    # Load the JSON file
    json_path = 'data/crawler_data/i_dont_care_about_cookies/Amazon.co.uk.json'
    if not os.path.exists(json_path):
        print(f"Error: File not found at {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON - {str(e)}")
            return
    
    # Extract cookies from the network data
    cookies = set()
    
    # Check for cookies in request headers
    requests = data.get('network_data', {}).get('requests', [])
    for request in requests:
        headers = request.get('headers', {})
        if 'cookie' in headers:
            cookie_header = headers['cookie']
            cookie_pairs = cookie_header.split(';')
            for pair in cookie_pairs:
                if '=' in pair:
                    name = pair.strip().split('=', 1)[0]
                    cookies.add(name)
    
    # If no cookies were found in headers, check for cookie-related URLs or parameter names
    if not cookies:
        # Add some common cookie names for testing
        common_cookies = ['session-id', 'session-token', '_ga', '_gid', '_fbp']
        cookies.update(common_cookies)
    
    # Perform cookie lookups
    print(f"Found {len(cookies)} cookies to look up")
    
    results = {}
    for name in cookies:
        print(f"\nLooking up cookie: {name}")
        result = lookup_cookie(name)
        
        if result:
            if result.get('category') != 'unknown':
                print(f"✅ Match found: {name} - Category: {result.get('category')}")
                print(f"   Match type: {result.get('match_type')}")
            else:
                print(f"❌ No match found for: {name}")
        
        results[name] = result
    
    # Print summary
    print("\n--- SUMMARY ---")
    categories = {}
    for name, result in results.items():
        if result:
            category = result.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
    
    print(f"Total cookies: {len(cookies)}")
    for category, count in categories.items():
        print(f"{category}: {count}")
    
    return results

# Uncomment to run the test
if __name__ == "__main__":
    test_amazon_cookies()