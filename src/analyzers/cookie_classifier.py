import os
import json
import sys
from typing import Dict, Any, Set
from tqdm import tqdm
from collections import Counter
from datetime import datetime

# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


from src.managers.cookie_manager import CookieManager
from src.crawler.cookie_crawler import CookieCrawler


class CookieClassifier:
    """
    Classifies cookies found on websites by looking them up in the cookie database.
    Uses CookieCrawler to look up cookies not found in the database.
    Generates analysis and statistics for cookie usage on websites.
    """
    
    def __init__(self, cookie_manager=None, crawler=None, verbose=False):
        """
        Initialize the cookie classifier.
        
        Args:
            database: CookieDatabase instance to use (creates a new one if None)
            crawler: CookieCrawler instance to use (creates a new one if None)
            verbose: Whether to print detailed information during processing
        """
        self.cookie_manager = cookie_manager or CookieManager()
        self.crawler = crawler
        self.unknown_cookies = set()  # Track unknown cookies for batch lookup
        self.verbose = verbose
    
    def _init_crawler(self):
        """Initialize the crawler if it doesn't exist already"""
        if self.crawler is None:
            if self.verbose:
                tqdm.write("Initializing browser for cookie lookups...")
            self.crawler = CookieCrawler(database=self.cookie_manager)
    
    def classify_file(self, file_path: str, save_result=True, lookup_unknown=True) -> Dict[str, Any]:
        """
        Classify cookies in a website crawl file.
        
        Args:
            file_path: Path to the website crawl JSON file
            save_result: Whether to save the result back to the file
            lookup_unknown: Whether to look up unknown cookies
            
        Returns:
            Website data with added cookie analysis
        """
        try:
            # Load website data
            with open(file_path, 'r', encoding='utf-8') as f:
                site_data = json.load(f)
            
            # Get the site name for display
            site_name = site_data.get('domain', os.path.basename(file_path).replace('.json', ''))
            if self.verbose:
                tqdm.write(f"\nProcessing site: {site_name}")
                
            # Extract and track unknown cookies
            unknown_cookies = self._extract_unknown_cookies(site_data)
            if unknown_cookies:
                self.unknown_cookies.update(unknown_cookies)
                if self.verbose:
                    tqdm.write(f"Found {len(unknown_cookies)} unknown cookies in {site_name}")
                
            # Classify cookies using current database
            self._classify_site(site_data)
            
            # Save result if requested
            if save_result:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(site_data, f, indent=2)
                    
            return site_data
        except Exception as e:
            tqdm.write(f"Error classifying file {file_path}: {str(e)}")
            import traceback
            tqdm.write(traceback.format_exc())
            return {}
    
    def _extract_unknown_cookies(self, site_data: Dict[str, Any]) -> Set[str]:
        """Extract cookies not in the database"""
        unknown_cookies = set()
        
        # Extract all cookies from the site data
        all_cookies = []
        if 'cookies' in site_data and isinstance(site_data['cookies'], dict):
            # Format: {'visit1': [cookies], 'visit2': [cookies]}
            for visit_cookies in site_data['cookies'].values():
                all_cookies.extend(visit_cookies)
        elif 'cookies' in site_data and isinstance(site_data['cookies'], list):
            # Simple list format
            all_cookies = site_data['cookies']
        
        # Find cookies not in the database
        for cookie in all_cookies:
            cookie_name = cookie.get('name', '')
            if not cookie_name:
                continue
                
            if not self.cookie_manager.contains(cookie_name):
                unknown_cookies.add(cookie_name)
        
        return unknown_cookies
    
    def classify_directory(self, directory: str, lookup_unknown=True) -> Dict[str, Dict[str, Any]]:
        """
        Classify cookies in all JSON files in a directory.
        
        Args:
            directory: Path to directory containing website crawl JSON files
            lookup_unknown: Whether to look up unknown cookies
            
        Returns:
            Dictionary mapping filenames to their website data
        """
        results = {}
        self.unknown_cookies.clear()
        
        # Get all JSON files in the directory
        json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
        if self.verbose:
            tqdm.write(f"Found {len(json_files)} JSON files to process")
        
        # First pass: classify with existing database and gather unknown cookies
        for file_name in tqdm(json_files, desc="Classifying websites (first pass)"):
            file_path = os.path.join(directory, file_name)
            site_data = self.classify_file(file_path, lookup_unknown=False)
            results[file_name] = site_data
        
        # Look up unknown cookies if requested
        if lookup_unknown and self.unknown_cookies:
            if self.verbose:
                tqdm.write(f"\nFound {len(self.unknown_cookies)} unique unknown cookies across all sites")
            
            # Initialize crawler if needed
            self._init_crawler()
            
            # Look up unknown cookies
            if self.verbose:
                tqdm.write("Looking up unknown cookies...")
            self.crawler.lookup_cookies_batch(list(self.unknown_cookies))
            
            # Second pass: re-classify with updated database
            if self.verbose:
                tqdm.write("\nRe-classifying websites with updated database...")
            for file_name in tqdm(json_files, desc="Classifying websites (final pass)"):
                file_path = os.path.join(directory, file_name)
                site_data = self.classify_file(file_path, lookup_unknown=False)
                results[file_name] = site_data
                
                # Print summary for this site
                if self.verbose and 'cookie_analysis' in site_data:
                    self.print_site_summary(site_data)
        else:
            # Print summaries for first pass
            if self.verbose:
                for file_name, site_data in results.items():
                    if 'cookie_analysis' in site_data:
                        self.print_site_summary(site_data)
        
        return results
    
    def print_site_summary(self, site_data: Dict[str, Any]) -> None:
        """Print a summary of cookie analysis for a site"""
        analysis = site_data.get('cookie_analysis', {})
        main_site = site_data.get('domain', '')
        
        tqdm.write(f"\nCookie analysis for {main_site}:")
        tqdm.write(f"Total cookies: {analysis.get('total_cookies', 0)}")
        
        identified = analysis.get('identified_cookies', 0)
        total = analysis.get('total_cookies', 0)
        if total > 0:
            percentage = (identified/total*100)
            tqdm.write(f"Identified cookies: {identified} ({percentage:.1f}%)")
        
        if 'categories' in analysis:
            tqdm.write("\nTop cookie categories:")
            sorted_categories = sorted(analysis['categories'].items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_categories[:5]:
                if total > 0:
                    percentage = (count/total*100)
                    tqdm.write(f"  - {category}: {count} ({percentage:.1f}%)")
                else:
                    tqdm.write(f"  - {category}: {count}")
        
        if 'scripts' in analysis:
            tqdm.write("\nTop cookie providers:")
            sorted_scripts = sorted(analysis['scripts'].items(), key=lambda x: x[1], reverse=True)
            for script, count in sorted_scripts[:5]:
                if script != "Not specified" and total > 0:
                    percentage = (count/total*100)
                    tqdm.write(f"  - {script}: {count} ({percentage:.1f}%)")
    
    def _classify_site(self, site_data: Dict[str, Any]) -> None:
        """
        Classify cookies in a website data dictionary.
        
        Args:
            site_data: Website data dictionary
        """
        # Initialize cookie statistics
        stats = {
            'total_cookies': 0,
            'identified_cookies': 0,
            'categories': {},
            'scripts': {},
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Extract all cookies from the site data
        all_cookies = []
        if 'cookies' in site_data and isinstance(site_data['cookies'], dict):
            # Format: {'visit1': [cookies], 'visit2': [cookies]}
            for visit_cookies in site_data['cookies'].values():
                all_cookies.extend(visit_cookies)
        elif 'cookies' in site_data and isinstance(site_data['cookies'], list):
            # Simple list format
            all_cookies = site_data['cookies']
        
        stats['total_cookies'] = len(all_cookies)
        
        # Create a set to track unique cookies by name+domain
        unique_cookies = set()
        classified_cookies = []
        
        # Analyze each cookie
        for cookie in all_cookies:
            cookie_name = cookie.get('name', '')
            cookie_domain = cookie.get('domain', '')
            
            # Skip if no name
            if not cookie_name:
                continue
                
            # Normalize the domain by removing leading dot and www
            if cookie_domain:
                cookie_domain = cookie_domain.lstrip('.')
                if cookie_domain.startswith('www.'):
                    cookie_domain = cookie_domain[4:]
            
            # Skip if we've already analyzed this cookie
            cookie_key = f"{cookie_name}:{cookie_domain}"
            if cookie_key in unique_cookies:
                continue
            unique_cookies.add(cookie_key)
            
            # Get cookie information from database
            cookie_info = self.cookie_manager.get(cookie_name)
            
            # Create a copy of the cookie data
            classified_cookie = cookie.copy()
            
            if cookie_info:
                # Found in database
                category = cookie_info.get('category', 'Unknown')
                script = cookie_info.get('script', 'Not specified')
                
                # Add classification details
                classified_cookie['classification'] = {
                    'category': category,
                    'script': script,
                    'script_url': cookie_info.get('script_url', 'Not specified'),
                    'description': cookie_info.get('description', 'Not specified'),
                    'match_type': cookie_info.get('match_type', 'none')
                }
                
                # Update statistics
                stats['identified_cookies'] += 1
                stats['categories'][category] = stats['categories'].get(category, 0) + 1
                stats['scripts'][script] = stats['scripts'].get(script, 0) + 1
            else:
                # Not found in database
                classified_cookie['classification'] = {
                    'category': 'Unknown',
                    'script': 'Not specified',
                    'script_url': 'Not specified',
                    'description': 'No match found in database',
                    'match_type': 'none'
                }
                
                # Update statistics
                stats['categories']['Unknown'] = stats['categories'].get('Unknown', 0) + 1
                stats['scripts']['Not specified'] = stats['scripts'].get('Not specified', 0) + 1
                
            classified_cookies.append(classified_cookie)
        
        # Update site data
        site_data['cookies'] = classified_cookies
        site_data['cookie_analysis'] = stats
    
    def close(self):
        """Close resources"""
        if self.crawler:
            self.crawler.close()
            self.crawler = None

# Standalone execution
if __name__ == "__main__":
    if len(sys.argv) > 1:
        data_directory = sys.argv[1]
    else:
        # Default directory
        data_directory = 'data/crawler_data/i_dont_care_about_cookies'
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        tqdm.write(f"Error: Directory not found: {data_directory}")
        tqdm.write("Please ensure the data directory exists before running the script.")
        sys.exit(1)
        
    try:
        # Print database stats
        cookie_manager = CookieManager()
        stats = cookie_manager.get_statistics()
        tqdm.write(f"Cookie database contains {stats['total_cookies']} cookies")
        
        # Create classifier and process directory
        classifier = CookieClassifier(cookie_manager, verbose=True)
        try:
            classifier.classify_directory(data_directory, lookup_unknown=True)
        finally:
            # Ensure resources are closed
            classifier.close()
        
        tqdm.write("\nClassification complete!")
    except KeyboardInterrupt:
        tqdm.write("\nClassification interrupted by user.")
        sys.exit(0)