import os
import json
import sys
import logging
from tqdm import tqdm
import time
from concurrent.futures import ProcessPoolExecutor, as_completed


# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


from src.analyzers.screenshot_analyzer import analyze_screenshots
from src.analyzers.html_analyzer import analyze_cookie_consent_text
from src.analyzers.check_page_loaded import check_domain_screenshots


# Configure logging - only show warnings and above by default
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BannerAnalyzer:
    """Class to analyze banner data from screenshots and HTML"""
    
    def __init__(self, banner_data_dir="data/banner_data", crawler_data_dir="data/crawler_data"):
        """Initialize with paths to data directories"""
        self.banner_data_dir = banner_data_dir
        self.crawler_data_dir = crawler_data_dir
        self.extension_folders = self.get_extension_folders()
    
    def get_domains_to_analyze(self, test_domain=None, test_count=None):
        """Get the list of domains to analyze based on available data"""
        screenshot_dir = os.path.join(self.banner_data_dir, "screenshots")
        html_dir = os.path.join(self.banner_data_dir, "html")
        
        domains = []
        if os.path.exists(screenshot_dir):
            domains.extend([d for d in os.listdir(screenshot_dir) 
                          if os.path.isdir(os.path.join(screenshot_dir, d))])
        if os.path.exists(html_dir):
            domains.extend([d for d in os.listdir(html_dir) 
                          if os.path.isdir(os.path.join(html_dir, d))])
        
        # Get unique domains
        domains = list(set(domains))
        
        # Filter to only test domain if specified
        if test_domain:
            if test_domain in domains:
                domains = [test_domain]
            else:
                logger.warning(f"Test domain '{test_domain}' not found in available domains.")
                return []
        
        if not domains:
            logger.warning("No domains found to analyze.")
        
        # Limit to test_count domains if specified
        if test_count and not test_domain and len(domains) > test_count:
            domains = domains[:test_count]
        
        return domains
    
    def get_extension_folders(self):
        """Get the list of extension folders from the crawler data directory"""
        if not os.path.exists(self.crawler_data_dir):
            logger.error(f"Crawler data directory not found: {self.crawler_data_dir}")
            return []
            
        extension_folders = [f for f in os.listdir(self.crawler_data_dir) 
                            if os.path.isdir(os.path.join(self.crawler_data_dir, f))]
        
        if not extension_folders:
            logger.warning(f"No extension folders found in {self.crawler_data_dir}")
        
        return extension_folders
    
    def analyze_domain(self, domain):
        """Analyze a single domain's screenshots and HTML data"""
        screenshot_dir = os.path.join(self.banner_data_dir, "screenshots")
        html_dir = os.path.join(self.banner_data_dir, "html")
        
        # Paths for this domain
        domain_screenshot_dir = os.path.join(screenshot_dir, domain)
        domain_html_dir = os.path.join(html_dir, domain)
        
        # Check if directories exist
        screenshots_exist = os.path.exists(domain_screenshot_dir)
        html_exists = os.path.exists(domain_html_dir)
        
        if not screenshots_exist and not html_exists:
            logger.warning(f"No data found for domain {domain}, skipping")
            return {}
        
        # Analyze screenshots
        screenshot_results = {}
        page_loaded_results = {}
        if screenshots_exist:
            if os.listdir(domain_screenshot_dir):
                screenshot_results = analyze_screenshots(domain_screenshot_dir)
                
                # Add page load check
                page_loaded_results = check_domain_screenshots(domain_screenshot_dir)
        
        # Analyze HTML
        html_results = {}
        if html_exists:
            if os.listdir(domain_html_dir):
                html_results = analyze_cookie_consent_text(domain_html_dir)
        
        # Process results to create the banner_results structure
        banner_results = self.process_domain_results(
            screenshot_results, 
            html_results, 
            page_loaded_results
        )
        
        return banner_results
    
    def is_file_for_extension(self, filename, ext_key):
        """
        Determine if a file belongs to a specific extension based on filename pattern.
        
        Args:
            filename (str): The filename to check
            ext_key (str): The extension key (lowercase, normalized)
            
        Returns:
            bool: True if the file belongs to this extension, False otherwise
        """
        # Get base filename without extension
        base_name = os.path.basename(filename)
        name_without_ext = os.path.splitext(base_name)[0]
        
        # Split by underscores and convert to lowercase
        parts = name_without_ext.lower().split('_')
        
        # Skip the first part (visit number)
        if len(parts) > 1:
            parts = parts[1:]
        
        # Check exact extension match
        if '_' in ext_key:
            # For multi-word extensions like "ublock_origin_lite"
            ext_parts = ext_key.split('_')
            
            # The filename should contain exactly these parts as a continuous sequence
            for i in range(len(parts) - len(ext_parts) + 1):
                if parts[i:i+len(ext_parts)] == ext_parts:
                    # We have an exact match, now check this isn't part of a longer extension name
                    if (i+len(ext_parts) == len(parts)) or (ext_parts == ['adblock'] and parts[i:i+2] != ['adblock', 'plus']):
                        return True
        else:
            # For single-word extensions like "adblock" or "ublock"
            if ext_key in parts:
                if len(parts) == 1 or (ext_key == 'adblock' and parts != ['adblock', 'plus']) or \
                   (ext_key == 'ublock' and parts != ['ublock', 'origin', 'lite']):
                    return True
                    
        return False
    
    def process_domain_results(self, screenshot_results, html_results, page_loaded_results):
        """Process domain results to create a structured banner_results dictionary"""
        # Create a banner results structure keyed by extension
        banner_results = {}
        
        # Process for each extension
        for ext_folder in self.extension_folders:
            # Create a normalized extension key
            ext_key = ext_folder.replace(" ", "_").lower()
            
            # Initialize results for this extension
            banner_results[ext_key] = {
                "img_match": {},
                "text_match": {},
                "page_loaded": {}
            }
            
            # Process screenshot analysis results
            if screenshot_results and "screenshot_check" in screenshot_results:
                for visit_id, visit_data in screenshot_results["screenshot_check"].items():
                    # Get the keywords found in the baseline
                    keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's screenshot results
                    for screenshot_file, banner_present in visit_data.get("extensions", {}).items():
                        # Check if this file belongs to this extension
                        if not self.is_file_for_extension(screenshot_file, ext_key):
                            continue
                            
                        # If we reach here, this file belongs to the current extension
                        if visit_id not in banner_results[ext_key]["img_match"]:
                            banner_results[ext_key]["img_match"][visit_id] = {
                                "matched": banner_present,
                                "keywords": keywords
                            }
            
            # Process HTML analysis results
            if html_results and "html_check" in html_results:
                for visit_id, visit_data in html_results["html_check"].items():
                    # Get the baseline matches and keywords
                    baseline_matches = visit_data.get("no_extension", {}).get("matches", [])
                    html_keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's HTML results
                    for html_file, html_data in visit_data.get("extensions", {}).items():
                        # Skip the baseline
                        if "no_extension" in html_file:
                            continue
                            
                        # Check if this file belongs to this extension
                        if not self.is_file_for_extension(html_file, ext_key):
                            continue
                        
                        matches = html_data.get("matches", [])
                        missing = html_data.get("missing", [])
                        
                        # Compare with baseline to determine if banner was removed
                        if baseline_matches and not matches:
                            banner_removed = True
                        elif not baseline_matches:
                            banner_removed = None  # Can't determine
                        else:
                            banner_removed = False
                        
                        if visit_id not in banner_results[ext_key]["text_match"]:
                            banner_results[ext_key]["text_match"][visit_id] = {
                                "baseline_matches": baseline_matches,
                                "extension_matches": matches,
                                "missing_matches": missing,
                                "banner_removed": banner_removed,
                                "keywords": html_keywords
                            }
            
            # Process page loaded results
            if page_loaded_results:
                for visit_id, visit_data in page_loaded_results.items():
                    for screenshot_file, screenshot_data in visit_data.items():
                        # Check if this file belongs to this extension
                        if not self.is_file_for_extension(screenshot_file, ext_key):
                            continue
                            
                        if visit_id not in banner_results[ext_key]["page_loaded"]:
                            banner_results[ext_key]["page_loaded"][visit_id] = {
                                "loaded": screenshot_data.get("loaded", False),
                                "status": screenshot_data.get("status", "unknown")
                            }
        
        return banner_results
    
    def update_extension_files(self, domain, banner_results, test_run=False):
        """Update the appropriate extension JSON files with banner analysis results"""
        
        # Try different domain filename formats
        domain_filenames = [
            f"{domain}.json",
            f"{domain.replace('.', '_')}.json",
            f"{domain.lower()}.json",
            f"{domain.lower().replace('www.', '')}.json"
        ]
        
        # Track how many extension folders we updated
        updated_count = 0
        
        for ext_folder in self.extension_folders:
            ext_key = ext_folder.replace(" ", "_").lower()
            ext_folder_path = os.path.join(self.crawler_data_dir, ext_folder)
            
            # Skip if this extension doesn't have any results for this domain
            if ext_key not in banner_results:
                continue
            
            # Find the domain file in this extension folder
            domain_file_path = None
            for filename in domain_filenames:
                test_path = os.path.join(ext_folder_path, filename)
                if os.path.exists(test_path):
                    domain_file_path = test_path
                    break
            
            if domain_file_path:
                try:
                    # Load existing data
                    with open(domain_file_path, 'r', encoding='utf-8') as f:
                        site_data = json.load(f)
                    
                    # Extract results for this specific extension
                    ext_results = banner_results[ext_key]
                    
                    # Create or update "banner_analysis" field
                    if "banner_analysis" not in site_data:
                        site_data["banner_analysis"] = {}
                    
                    # Add extension-specific results
                    site_data["banner_analysis"].update(ext_results)
                    
                    # Save the updated data
                    if not test_run:
                        with open(domain_file_path, 'w', encoding='utf-8') as f:
                            json.dump(site_data, f, indent=2)
                
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error updating {domain_file_path}: {e}")
            else:
                logger.debug(f"No file found for {domain} in {ext_folder}")
        
        if updated_count == 0:
            logger.warning(f"Could not update any files for domain {domain}")
    
    def process_domain_parallel(self, domain):
        """Helper function for parallel domain processing"""
        return domain, self.analyze_domain(domain)
    
    def analyze_all_banners(self, test_run=True, test_domain=None, test_count=None, 
                           use_parallel=False, max_workers=None):
        """Run analyses and update JSON files with banner analysis results"""
        # Get domains to analyze
        domains = self.get_domains_to_analyze(test_domain, test_count)
        if not domains:
            return []
        
        # Print minimal status at the start
        print(f"{'TEST MODE' if test_run else 'LIVE MODE'} - Processing {len(domains)} domains")
        if use_parallel:
            print(f"Using parallel processing with {max_workers or 'auto'} workers")
        
        # Track timing
        start_time = time.time()
        
        if use_parallel and len(domains) > 1:
            # Setup to collect all results
            domain_results = {}
            total = len(domains)
            completed = 0
            
            # Create progress bar
            progress_bar = tqdm(total=total, desc="Analyzing domains")
            
            # Process domains in parallel
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks - note we need to use a non-method function for parallel processing
                future_to_domain = {
                    executor.submit(analyze_domain_parallel, domain, self.banner_data_dir, self.extension_folders): domain 
                    for domain in domains
                }
                
                # Process results as they complete
                for future in as_completed(future_to_domain):
                    domain = future_to_domain[future]
                    try:
                        banner_results = future.result()
                        domain_results[domain] = banner_results
                        
                        # Update progress bar
                        completed += 1
                        progress_bar.update(1)
                        progress_bar.set_postfix({"Current": domain})
                    except Exception as e:
                        logger.error(f"Error processing domain {domain}: {e}")
            
            # Close progress bar
            progress_bar.close()
            
            # Update extension files with results
            print("Updating extension files...")
            with tqdm(total=len(domain_results), desc="Updating extension files") as update_progress:
                for domain, banner_results in domain_results.items():
                    if banner_results:  # Only update if we have results
                        self.update_extension_files(domain, banner_results, test_run)
                    update_progress.update(1)
                    update_progress.set_postfix({"Current": domain})
        else:
            # Process domains sequentially with a progress bar
            for domain in tqdm(domains, desc="Analyzing domains"):
                banner_results = self.analyze_domain(domain)
                if banner_results:  # Only update if we have results
                    self.update_extension_files(domain, banner_results, test_run)
        
        # Report completion time
        elapsed_time = time.time() - start_time
        print(f"\nCompleted analysis of {len(domains)} domains in {elapsed_time:.2f} seconds")
        
        return domains  # Return the list of domains processed

    def analyze_single_extension(self, domain, extension_name, test_run=True):
        """
        Analyze a single domain with a specific extension for testing purposes
        
        Args:
            domain (str): The domain to analyze
            extension_name (str): The name of the extension to focus on
            test_run (bool): Whether to actually update files or just test
            
        Returns:
            dict: The banner analysis results
        """
        print(f"Analyzing domain {domain} with extension {extension_name}")
        
        # Analyze the domain
        banner_results = self.analyze_domain(domain)
        
        if not banner_results:
            print(f"No results found for domain {domain}")
            return {}
            
        # Extract just the extension we want to test
        ext_key = extension_name.replace(" ", "_").lower()
        if ext_key in banner_results:
            filtered_results = {ext_key: banner_results[ext_key]}
            
            # Display some results for verification
            print(f"\nResults for {extension_name} on {domain}:")
            
            # Show image match results if available
            img_matches = banner_results[ext_key].get("img_match", {})
            if img_matches:
                print(f"  Image matches: {len(img_matches)} visits analyzed")
                for visit_id, data in img_matches.items():
                    print(f"    Visit {visit_id}: {len(data)} screenshots")
            else:
                print("  No image matches found")
                
            # Show text match results if available
            text_matches = banner_results[ext_key].get("text_match", {})
            if text_matches:
                print(f"  Text matches: {len(text_matches)} visits analyzed")
                for visit_id, data in text_matches.items():
                    print(f"    Visit {visit_id}: {len(data)} HTML files")
            else:
                print("  No text matches found")
            
            # Update extension files if requested
            if not test_run:
                self.update_extension_files(domain, filtered_results, test_run=False)
                print(f"Updated files for {domain} with {extension_name} results")
            else:
                print("Test run - no files updated")
                
            return filtered_results
        else:
            print(f"No results found for extension {extension_name}")
            return {}


# Helper function for parallel processing (needs to be outside the class)
def analyze_domain_parallel(domain, banner_data_dir, extension_folders):
    """
    Helper function for parallel domain processing that doesn't rely on class methods
    This is needed because class methods can't be pickled for multiprocessing
    """

    
    screenshot_dir = os.path.join(banner_data_dir, "screenshots")
    html_dir = os.path.join(banner_data_dir, "html")
    
    # Paths for this domain
    domain_screenshot_dir = os.path.join(screenshot_dir, domain)
    domain_html_dir = os.path.join(html_dir, domain)
    
    # Check if directories exist
    screenshots_exist = os.path.exists(domain_screenshot_dir)
    html_exists = os.path.exists(domain_html_dir)
    
    if not screenshots_exist and not html_exists:
        logger.warning(f"No data found for domain {domain}, skipping")
        return {}
    
    # Analyze screenshots
    screenshot_results = {}
    page_loaded_results = {}
    if screenshots_exist and os.listdir(domain_screenshot_dir):
        screenshot_results = analyze_screenshots(domain_screenshot_dir)
        page_loaded_results = check_domain_screenshots(domain_screenshot_dir)
    
    # Analyze HTML
    html_results = {}
    if html_exists and os.listdir(domain_html_dir):
        html_results = analyze_cookie_consent_text(domain_html_dir)
    
    # Process domain results
    def process_domain_results(screenshot_results, html_results, page_loaded_results, extension_folders):
        # Create a banner results structure keyed by extension
        banner_results = {}
        
        # Helper function for extension matching
        def is_file_for_extension(filename, ext_key):
            """
            Determine if a file belongs to a specific extension based on filename pattern.
            
            Args:
                filename (str): The filename to check
                ext_key (str): The extension key (lowercase, normalized)
                
            Returns:
                bool: True if the file belongs to this extension, False otherwise
            """
            # Get base filename without extension
            base_name = os.path.basename(filename)
            name_without_ext = os.path.splitext(base_name)[0]
            
            # Split by underscores and convert to lowercase
            parts = name_without_ext.lower().split('_')
            
            # Skip the first part (visit number)
            if len(parts) > 1:
                parts = parts[1:]
            
            # Check exact extension match
            if '_' in ext_key:
                # For multi-word extensions like "ublock_origin_lite"
                ext_parts = ext_key.split('_')
                
                # The filename should contain exactly these parts as a continuous sequence
                for i in range(len(parts) - len(ext_parts) + 1):
                    if parts[i:i+len(ext_parts)] == ext_parts:
                        # We have an exact match, now check this isn't part of a longer extension name
                        if (i+len(ext_parts) == len(parts)) or (ext_parts == ['adblock'] and parts[i:i+2] != ['adblock', 'plus']):
                            return True
            else:
                # For single-word extensions like "adblock" or "ublock"
                if ext_key in parts:
                    if len(parts) == 1 or (ext_key == 'adblock' and parts != ['adblock', 'plus']) or \
                       (ext_key == 'ublock' and parts != ['ublock', 'origin', 'lite']):
                        return True
                    
            return False
        
        # Process for each extension
        for ext_folder in extension_folders:
            # Create a normalized extension key
            ext_key = ext_folder.replace(" ", "_").lower()
            
            # Initialize results for this extension
            banner_results[ext_key] = {
                "img_match": {},
                "text_match": {},
                "page_loaded": {}
            }
            
            # Process screenshot analysis results
            if screenshot_results and "screenshot_check" in screenshot_results:
                for visit_id, visit_data in screenshot_results["screenshot_check"].items():
                    # Get the keywords found in the baseline
                    keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's screenshot results
                    for screenshot_file, banner_present in visit_data.get("extensions", {}).items():
                        # Check if this file belongs to this extension
                        if not is_file_for_extension(screenshot_file, ext_key):
                            continue
                            
                        # If we reach here, this file belongs to the current extension
                        if visit_id not in banner_results[ext_key]["img_match"]:
                            banner_results[ext_key]["img_match"][visit_id] = {
                                "matched": banner_present,
                                "keywords": keywords
                            }
            
            # Process HTML analysis results
            if html_results and "html_check" in html_results:
                for visit_id, visit_data in html_results["html_check"].items():
                    # Get the baseline matches and keywords
                    baseline_matches = visit_data.get("no_extension", {}).get("matches", [])
                    html_keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's HTML results
                    for html_file, html_data in visit_data.get("extensions", {}).items():
                        # Skip the baseline
                        if "no_extension" in html_file:
                            continue
                            
                        # Check if this file belongs to this extension
                        if not is_file_for_extension(html_file, ext_key):
                            continue
                        
                        matches = html_data.get("matches", [])
                        missing = html_data.get("missing", [])
                        
                        # Compare with baseline to determine if banner was removed
                        if baseline_matches and not matches:
                            banner_removed = True
                        elif not baseline_matches:
                            banner_removed = None  # Can't determine
                        else:
                            banner_removed = False
                        
                        if visit_id not in banner_results[ext_key]["text_match"]:
                            banner_results[ext_key]["text_match"][visit_id] = {
                                "baseline_matches": baseline_matches,
                                "extension_matches": matches,
                                "missing_matches": missing,
                                "banner_removed": banner_removed,
                                "keywords": html_keywords
                            }
            
            # Process page loaded results
            if page_loaded_results:
                for visit_id, visit_data in page_loaded_results.items():
                    for screenshot_file, screenshot_data in visit_data.items():
                        # Check if this file belongs to this extension
                        if not is_file_for_extension(screenshot_file, ext_key):
                            continue
                            
                        if visit_id not in banner_results[ext_key]["page_loaded"]:
                            banner_results[ext_key]["page_loaded"][visit_id] = {
                                "loaded": screenshot_data.get("loaded", False),
                                "status": screenshot_data.get("status", "unknown")
                            }
        
        return banner_results
    
    # Process the results
    banner_results = process_domain_results(
        screenshot_results, 
        html_results, 
        page_loaded_results, 
        extension_folders
    )
    
    return banner_results

if __name__ == "__main__":
    # Comment out the default test configuration
    """
    cpu_count = multiprocessing.cpu_count()
    recommended_workers = max(1, cpu_count - 1)  # Leave one CPU for system
    
    # Create the analyzer
    analyzer = BannerAnalyzer()
    
    # Run the analysis
    analyzer.analyze_all_banners(
        test_run=True,                 # Set to False to actually update files
        test_count=5,                  # Process 5 domains for quick testing
        use_parallel=True,             # Process domains in parallel 
        max_workers=5
    )
    """
    
    # Single extension test code
    analyzer = BannerAnalyzer()
    
    # Choose a domain and extension to test
    test_domain = "amazon.co.uk"  # Replace with an actual domain in your dataset
    test_extension = "adblock"
    
    # Run the single extension test
    results = analyzer.analyze_single_extension(
        domain=test_domain,
        extension_name=test_extension,
        test_run=False
    )
    
    print("\nTest completed")