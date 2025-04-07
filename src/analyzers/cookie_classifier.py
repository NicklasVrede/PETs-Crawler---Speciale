import os
import json
import sys
from typing import Dict, Any, Set
from tqdm import tqdm
from collections import Counter, defaultdict
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
        tqdm.write(f"Unique cookies: {analysis.get('unique_cookies', 0)}")
        
        if 'overlapping_cookies' in analysis:
            tqdm.write(f"Cookies present in multiple visits: {analysis.get('overlapping_cookies', 0)}")
        
        identified = analysis.get('identified_cookies', 0)
        unique = analysis.get('unique_cookies', 0)
        if unique > 0:
            percentage = (identified/unique*100)
            tqdm.write(f"Identified cookies: {identified} ({percentage:.1f}%)")
        
        if 'categories' in analysis:
            tqdm.write("\nTop cookie categories:")
            sorted_categories = sorted(analysis['categories'].items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_categories[:5]:
                if unique > 0:
                    percentage = (count/unique*100)
                    tqdm.write(f"  - {category}: {count} ({percentage:.1f}%)")
                else:
                    tqdm.write(f"  - {category}: {count}")
        
        if 'scripts' in analysis:
            tqdm.write("\nTop cookie providers:")
            sorted_scripts = sorted(analysis['scripts'].items(), key=lambda x: x[1], reverse=True)
            for script, count in sorted_scripts[:5]:
                if script != "Not specified" and unique > 0:
                    percentage = (count/unique*100)
                    tqdm.write(f"  - {script}: {count} ({percentage:.1f}%)")
    
    def _classify_site(self, site_data: Dict[str, Any]) -> None:
        """
        Classify cookies in a website data dictionary.
        
        Args:
            site_data: Website data dictionary
        """
        # Initialize cookie statistics
        stats = {
            'unique_cookies': 0,
            'overlapping_cookies': 0,
            'identified_cookies': 0,
            'unidentified_cookies': 0, 
            'categories': {},
            'scripts': {},
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Sets to track unique cookies
        all_cookies = []
        unique_cookie_names = set()
        identified_cookie_names = set()
        unidentified_cookie_names = set()  # Track unidentified cookies
        category_counts = defaultdict(set)
        script_counts = defaultdict(set)
        
        # Track cookies by visit for overlap analysis
        cookies_by_visit = defaultdict(set)
        
        # Process cookies based on their structure
        if 'cookies' in site_data:
            if isinstance(site_data['cookies'], dict):
                # Format: {'visit1': [cookies], 'visit2': [cookies]}
                # Create a new dict to hold classified cookies with same structure
                classified_cookies_dict = {}
                
                for visit_id, visit_cookies in site_data['cookies'].items():
                    all_cookies.extend(visit_cookies)
                    classified_cookies_dict[visit_id] = []
                    
                    # Classify cookies for this visit
                    for cookie in visit_cookies:
                        cookie_name = cookie.get('name', '')
                        if cookie_name:
                            unique_cookie_names.add(cookie_name)
                            cookies_by_visit[visit_id].add(cookie_name)
                        
                        classified_cookie = self._classify_cookie(cookie, stats, 
                                                                identified_cookie_names,
                                                                unidentified_cookie_names,
                                                                category_counts, 
                                                                script_counts)
                        classified_cookies_dict[visit_id].append(classified_cookie)
                
                # Update site data with classified cookies
                site_data['cookies'] = classified_cookies_dict
                
            elif isinstance(site_data['cookies'], list):
                # Simple list format
                all_cookies = site_data['cookies']
                classified_cookies = []
                
                # Classify each cookie
                for cookie in all_cookies:
                    cookie_name = cookie.get('name', '')
                    if cookie_name:
                        unique_cookie_names.add(cookie_name)
                        cookies_by_visit['visit0'].add(cookie_name)  # Single visit
                    
                    classified_cookie = self._classify_cookie(cookie, stats,
                                                            identified_cookie_names,
                                                            unidentified_cookie_names,
                                                            category_counts,
                                                            script_counts)
                    classified_cookies.append(classified_cookie)
                
                # Update site data with classified cookies
                site_data['cookies'] = classified_cookies
        
            # Calculate overlap between visits
            overlapping_cookies = set()
            if len(cookies_by_visit) > 1:
                # Find cookies that appear in multiple visits
                visit_ids = list(cookies_by_visit.keys())
                for i in range(len(visit_ids)):
                    for j in range(i+1, len(visit_ids)):
                        overlapping_cookies.update(
                            cookies_by_visit[visit_ids[i]] & cookies_by_visit[visit_ids[j]]
                        )
            
            # Set cookie counts in stats
            stats['unique_cookies'] = len(unique_cookie_names)
            stats['overlapping_cookies'] = len(overlapping_cookies)  # Moved here to maintain order
            stats['identified_cookies'] = len(identified_cookie_names)
            stats['unidentified_cookies'] = len(unidentified_cookie_names)
            
            # Update category and script counts with the correct unique count
            for category, cookies in category_counts.items():
                stats['categories'][category] = len(cookies)
            
            for script, cookies in script_counts.items():
                stats['scripts'][script] = len(cookies)
        
            # Add note about categories representing cookies across all visits
            stats['note'] = "Category and script counts represent unique cookies across all visits"
        
        # Add cookie analysis to site data
        site_data['cookie_analysis'] = stats
    
    def _classify_cookie(self, cookie: Dict[str, Any], stats: Dict[str, Any], 
                        identified_cookies: Set[str], unidentified_cookies: Set[str],
                        category_counts: Dict[str, Set[str]], 
                        script_counts: Dict[str, Set[str]]) -> Dict[str, Any]:
        """
        Classify a single cookie and update statistics.
        
        Args:
            cookie: Cookie data
            stats: Statistics dictionary to update
            identified_cookies: Set of cookie names that have been identified
            unidentified_cookies: Set of cookie names that were not identified
            category_counts: Dictionary mapping categories to sets of cookie names
            script_counts: Dictionary mapping scripts to sets of cookie names
            
        Returns:
            Classified cookie data
        """
        cookie_name = cookie.get('name', '')
        cookie_domain = cookie.get('domain', '')
        
        # Create a copy of the cookie data
        classified_cookie = cookie.copy()
        
        # Skip if no name
        if not cookie_name:
            return classified_cookie
        
        # Normalize the domain by removing leading dot and www
        if cookie_domain:
            cookie_domain = cookie_domain.lstrip('.')
            if cookie_domain.startswith('www.'):
                cookie_domain = cookie_domain[4:]
        
        # Get cookie information from database
        cookie_info = self.cookie_manager.get(cookie_name)
        
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
            
            # Update statistics tracking sets
            identified_cookies.add(cookie_name)
            category_counts[category].add(cookie_name)
            script_counts[script].add(cookie_name)
        else:
            # Not found in database - explicitly mark as Unidentified
            classified_cookie['classification'] = {
                'category': 'Unidentified',  # Changed from Unknown to Unidentified
                'script': 'Not specified',
                'script_url': 'Not specified',
                'description': 'No match found in database',
                'match_type': 'none'
            }
            
            # Update statistics tracking sets
            unidentified_cookies.add(cookie_name)
            category_counts['Unidentified'].add(cookie_name)  # Use Unidentified category
            script_counts['Not specified'].add(cookie_name)
        
        return classified_cookie
    
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
        data_directory = 'data/crawler_data/test'
    
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