import os
import json
import sys
from tqdm import tqdm
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import cv2  # Add this import at the top with the other imports
import numpy as np


# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


from src.analyzers.screenshot_analyzer import analyze_screenshots
from src.analyzers.html_analyzer import analyze_cookie_consent_text
from src.analyzers.check_page_loaded import check_domain_screenshots

class BannerAnalyzer:
    """Class to analyze banner data from screenshots and HTML"""
    
    def __init__(self, banner_data_dir="data/banner_data", crawler_data_dir="data/crawler_data", verbose=False):
        """Initialize with paths to data directories"""
        self.banner_data_dir = banner_data_dir
        self.crawler_data_dir = crawler_data_dir
        self.verbose = verbose 
        self.extension_folders = self.get_extension_folders()

    def _log(self, message):
        """Log a message if verbose is True"""
        if self.verbose:
            print(message)
    
    def get_domains_to_analyze(self, test_domain=None, nr_domains=None):
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
                self._log(f"Test domain '{test_domain}' not found in available domains.")
                return []
        
        if not domains:
            self._log("No domains found to analyze.")
        
        # Limit to test_count domains if specified
        if nr_domains and not test_domain and len(domains) > nr_domains:
            domains = domains[:nr_domains]
        
        return domains
    
    def get_extension_folders(self):
        """Get the list of extension folders from the crawler data directory"""
        if not os.path.exists(self.crawler_data_dir):
            self._log(f"Crawler data directory not found: {self.crawler_data_dir}")
            return []
            
        extension_folders = [f for f in os.listdir(self.crawler_data_dir) 
                            if os.path.isdir(os.path.join(self.crawler_data_dir, f))]
        
        if not extension_folders:
            self._log(f"No extension folders found in {self.crawler_data_dir}")
        
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
            self._log(f"No data found for domain {domain}, skipping")
            return {}
        
        # First check if pages loaded properly
        page_loaded_results = {}
        if screenshots_exist and os.listdir(domain_screenshot_dir):
            page_loaded_results = check_domain_screenshots(domain_screenshot_dir)
        
        # Then analyze screenshots and HTML only if needed
        screenshot_results = {}
        if screenshots_exist and os.listdir(domain_screenshot_dir):
            screenshot_results = analyze_screenshots(domain_screenshot_dir)
        
        html_results = {}
        if html_exists and os.listdir(domain_html_dir):
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
        """Process domain results to create a structured banner_results dictionary by visit"""
        # Create a banner results structure keyed by extension
        banner_results = {}
        
        # Process for each extension
        for ext_folder in self.extension_folders:
            # Create a normalized extension key
            ext_key = ext_folder.replace(" ", "_").lower()
            
            # Initialize results for this extension
            banner_results[ext_key] = {}
            
            # Collect all visit IDs from all data sources
            all_visit_ids = set()
            if screenshot_results and "screenshot_check" in screenshot_results:
                all_visit_ids.update(screenshot_results["screenshot_check"].keys())
            if html_results and "html_check" in html_results:
                all_visit_ids.update(html_results["html_check"].keys())
            if page_loaded_results:
                all_visit_ids.update(page_loaded_results.keys())
            
            # Process each visit
            for visit_id in all_visit_ids:
                # Initialize the visit data structure
                banner_results[ext_key][visit_id] = {}
                
                # Process screenshot analysis results for this visit
                if screenshot_results and "screenshot_check" in screenshot_results and visit_id in screenshot_results["screenshot_check"]:
                    visit_data = screenshot_results["screenshot_check"][visit_id]
                    keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's screenshot results
                    for screenshot_file, ext_data in visit_data.get("extensions", {}).items():
                        # Check if this file belongs to this extension
                        if self.is_file_for_extension(screenshot_file, ext_key):
                            # Determine image match status - updated field names
                            if not keywords:
                                status = "no_baseline_keywords"
                            elif ext_data.get("removal_indicated", False):
                                status = "some_keywords_missing"
                            else:
                                status = "all_keywords_found"
                                
                            banner_results[ext_key][visit_id]["screenshot"] = status
                
                # Process HTML analysis results for this visit
                if html_results and "html_check" in html_results and visit_id in html_results["html_check"]:
                    visit_data = html_results["html_check"][visit_id]
                    keywords = visit_data.get("keywords", [])
                    
                    # Check each extension's HTML results
                    for html_file, ext_data in visit_data.get("extensions", {}).items():
                        # Check if this file belongs to this extension
                        if self.is_file_for_extension(html_file, ext_key):
                            # Determine text match status - updated field names
                            if not keywords:
                                status = "no_baseline_keywords"
                            elif ext_data.get("removal_indicated", False):
                                status = "some_keywords_missing"
                            else:
                                status = "all_keywords_found"
                            
                            banner_results[ext_key][visit_id]["html"] = status
                
                # Process page loaded results for this visit
                if page_loaded_results and visit_id in page_loaded_results:
                    for screenshot_file, screenshot_data in page_loaded_results[visit_id].items():
                        # Check if this file belongs to this extension
                        if self.is_file_for_extension(screenshot_file, ext_key):
                            banner_results[ext_key][visit_id]["page_loaded"] = screenshot_data.get("loaded", False)
                            banner_results[ext_key][visit_id]["page_status"] = screenshot_data.get("status", "unknown")
                
                # Generate conclusion for this visit
                page_loaded = banner_results[ext_key][visit_id].get("page_loaded", False)
                html = banner_results[ext_key][visit_id].get("html", "unknown")
                screenshot = banner_results[ext_key][visit_id].get("screenshot", "unknown")
                
                # Determine conclusion
                conclusion = "unknown"
                reason = ["Could not determine banner status"]
                
                if not page_loaded:
                    conclusion = "not_loaded"
                    reason = ["Page did not load properly"]
                elif html == "no_baseline_keywords" or screenshot == "no_baseline_keywords":
                    conclusion = "unknown"
                    reason = ["No banner keywords detected in baseline, cannot determine if banner was removed"]
                elif html == "no_keywords_found" or html == "some_keywords_missing":
                    conclusion = "removed"
                    reason = ["HTML analysis confirms banner elements were removed"]
                elif screenshot == "some_keywords_missing":
                    conclusion = "likely_removed"
                    reason = ["Screenshot analysis suggests banner is not visible but HTML elements may remain"]
                else:
                    conclusion = "not_removed"
                    reason = ["Both HTML and screenshot analyses indicate banner is still present"]
                
                # Add flattened conclusion to results
                banner_results[ext_key][visit_id]["conclusion"] = conclusion
                banner_results[ext_key][visit_id]["reason"] = reason
            
            # Add a flattened summary at the top level (not under a visit)
            summary_status, summary_reason = self.generate_summary(banner_results[ext_key])
            banner_results[ext_key]["summary_status"] = summary_status
            banner_results[ext_key]["summary_reason"] = summary_reason
        
        return banner_results
    
    def generate_summary(self, ext_results):
        """Generate a summary of results across all visits for an extension"""
        # Get all visit IDs
        all_visits = [v for v in ext_results.keys() if v not in ["summary_status", "summary_reason"]]
        
        if not all_visits:
            return "unknown", ["No visit data available"]
        
        # First check if any visits loaded successfully
        loaded_visits = [v for v in all_visits if ext_results.get(v, {}).get("page_loaded", False)]
        
        if not loaded_visits:
            # No visits loaded successfully
            return "not_loaded", ["None of the visits loaded successfully"]
        
        # Prioritize loaded visits for our conclusion
        removed_count = 0
        likely_removed_count = 0
        not_removed_count = 0
        unknown_count = 0
        
        for visit in loaded_visits:
            # Updated to use the flattened structure
            status = ext_results.get(visit, {}).get("conclusion", "unknown")
            if status == "removed":
                removed_count += 1
            elif status == "likely_removed":
                likely_removed_count += 1
            elif status == "not_removed":
                not_removed_count += 1
            else:
                unknown_count += 1
        
        # Determine overall conclusion
        total_loaded = len(loaded_visits)
        if removed_count > 0:
            # If any visit shows definite removal, consider it removed
            status = "removed"
            reason = [f"{removed_count}/{total_loaded} loaded visits showed banner removal"]
        elif likely_removed_count > 0:
            # If any visit shows likely removal, consider it likely removed
            status = "likely_removed"
            reason = [f"{likely_removed_count}/{total_loaded} loaded visits showed likely banner removal"]
        elif not_removed_count > 0:
            # If any visit shows no removal, consider it not removed
            status = "not_removed"
            reason = [f"{not_removed_count}/{total_loaded} loaded visits showed banner was not removed"]
        else:
            status = "unknown"
            reason = ["Could not determine if banner was removed"]
        
        # Return just the status and reason without confidence
        return status, reason
    
    def update_extension_files(self, domain, banner_results, test_run=False):
        """Update the appropriate extension JSON files with banner analysis results"""
        
        # Try different domain filename formats
        domain_filenames = [
            f"{domain}.json",
            f"{domain.replace('.', '_')}.json",
            f"{domain.lower()}.json",
            f"{domain.lower().replace('www.', '')}.json",
            f"www.{domain}.json" if not domain.startswith('www.') else None
        ]
        
        # Remove None entries that might exist
        domain_filenames = [f for f in domain_filenames if f]
        
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
                    tqdm.write(f"Error updating {domain_file_path}: {e}")
            else:
                self._log(f"No file found for {domain} in {ext_folder}")
        
        if updated_count == 0:
            self._log(f"Could not update any files for domain {domain}")
    
    def analyze_domain_wrapper(self, args):
        """
        A standalone wrapper function for multiprocessing that unpacks arguments and calls analyze_domain.
        This avoids pickling class methods directly.
        """
        domain, banner_data_dir, crawler_data_dir, extension_folders = args
        # Create a temporary analyzer just for this process
        temp_analyzer = BannerAnalyzer(banner_data_dir=banner_data_dir, crawler_data_dir=crawler_data_dir)
        temp_analyzer.extension_folders = extension_folders
        return domain, temp_analyzer.analyze_domain(domain)
    
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
                # Prepare args tuples - each contains everything the function needs
                args_list = [
                    (domain, self.banner_data_dir, self.crawler_data_dir, self.extension_folders) 
                    for domain in domains
                ]
                
                # Submit all tasks using the wrapper function
                future_to_domain = {
                    executor.submit(self.analyze_domain_wrapper, args): args[0] 
                    for args in args_list
                }
                
                # Process results as they complete
                for future in as_completed(future_to_domain):
                    domain = future_to_domain[future]
                    try:
                        domain_name, banner_results = future.result()
                        domain_results[domain_name] = banner_results
                        
                        # Update progress bar
                        completed += 1
                        progress_bar.update(1)
                        progress_bar.set_postfix({"Current": domain})
                    except Exception as e:
                        tqdm.write(f"Error processing domain {domain}: {e}")
            
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
        self._log(f"\nCompleted analysis of {len(domains)} domains in {elapsed_time:.2f} seconds")
        
        return domains  # Return the list of domains processed

    def analyze_single_extension(self, domain, extension_name, test_run=True):
        """Analyze a single domain with a specific extension"""
        # Find the extension folder
        ext_folder = None
        for folder in self.extension_folders:
            if folder.replace(" ", "_").lower() == extension_name.lower():
                ext_folder = folder
                break
        
        if not ext_folder:
            self._log(f"Extension '{extension_name}' not found in available extensions.")
            return None
        
        # Analyze the domain
        results = self.analyze_domain(domain)
        
        # Get results for this extension
        ext_key = extension_name.replace(" ", "_").lower()
        if ext_key in results:
            ext_results = results[ext_key]
            
            # Write results to file if not a test run
            if not test_run:
                self.write_extension_results(domain, ext_folder, ext_results)
            
            # Enhanced output for test run
            if test_run:
                print(f"\n=== Test Analysis for {domain} with {extension_name} ===")
                
                # Print summary results
                print(f"\nSummary Status: {ext_results.get('summary_status', 'unknown')}")
                print(f"Summary Reason: {', '.join(ext_results.get('summary_reason', ['Unknown']))}")
                
                # Print visit-specific results
                for key in ext_results:
                    if key.startswith("visit"):
                        visit_data = ext_results[key]
                        print(f"\n--- Visit {key} ---")
                        
                        # Check if page loaded
                        page_loaded = visit_data.get("page_loaded", False)
                        print(f"Page Loaded: {page_loaded}")
                        if not page_loaded:
                            print(f"Page Status: {visit_data.get('page_status', 'unknown')}")
                        
                        # HTML analysis results
                        html_status = visit_data.get("html", "unknown")
                        print(f"HTML Analysis: {html_status}")
                        
                        # Screenshot analysis results
                        screenshot_status = visit_data.get("screenshot", "unknown")
                        print(f"Screenshot Analysis: {screenshot_status}")
                        
                        # Conclusion
                        print(f"Conclusion: {visit_data.get('conclusion', 'unknown')}")
                        print(f"Reason: {', '.join(visit_data.get('reason', ['Unknown']))}")
                
                # Fetch and display the actual keywords from the source data
                self._print_detailed_keywords(domain, extension_name)
            else:
                print(f"Results for {domain} with {extension_name} saved successfully.")
            
            return ext_results
        else:
            self._log(f"No results found for extension '{extension_name}' on domain '{domain}'")
            return None

    def _print_detailed_keywords(self, domain, extension_name):
        """Print detailed keyword information from raw analysis data"""
        screenshot_dir = os.path.join(self.banner_data_dir, "screenshots", domain)
        html_dir = os.path.join(self.banner_data_dir, "html", domain)
        
        print("\n=== Raw Keyword Analysis ===")
        
        # Check for screenshot data
        if os.path.exists(screenshot_dir):
            print("\nScreenshot Keywords:")
            screenshot_results = analyze_screenshots(screenshot_dir, verbose=False)
            if "screenshot_check" in screenshot_results:
                for visit_id, visit_data in screenshot_results["screenshot_check"].items():
                    print(f"\n  Visit {visit_id}:")
                    print(f"  - Baseline Keywords: {', '.join(visit_data.get('keywords', ['None']))}")
                    
                    # Show extension results
                    for ext_file, ext_data in visit_data.get("extensions", {}).items():
                        if extension_name.lower() in ext_file.lower():
                            print(f"  - Extension '{ext_file}':")
                            print(f"    * Found Keywords: {', '.join(ext_data.get('screenshot', ['None']))}")
                            print(f"    * Banner Removal Indicated: {ext_data.get('removal_indicated', False)}")
        
        # Check for HTML data
        if os.path.exists(html_dir):
            print("\nHTML Keywords:")
            html_results = analyze_cookie_consent_text(html_dir, verbose=False)
            if "html_check" in html_results:
                for visit_id, visit_data in html_results["html_check"].items():
                    print(f"\n  Visit {visit_id}:")
                    print(f"  - Baseline Keywords: {', '.join(visit_data.get('keywords', ['None']))}")
                    
                    # Show extension results
                    for ext_file, ext_data in visit_data.get("extensions", {}).items():
                        if extension_name.lower() in ext_file.lower():
                            print(f"  - Extension '{ext_file}':")
                            print(f"    * Found Keywords: {', '.join(ext_data.get('html', ['None']))}")
                            print(f"    * Banner Removal Indicated: {ext_data.get('removal_indicated', False)}")

    def write_extension_results(self, domain, extension_folder, results):
        """Write extension results to a JSON file in the crawler data directory"""
        # Create path for the extension folder
        ext_dir = os.path.join(self.crawler_data_dir, extension_folder)
        os.makedirs(ext_dir, exist_ok=True)
        
        # Create JSON filepath
        json_file = os.path.join(ext_dir, f"{domain}.json")
        
        # Load existing data if available
        existing_data = {}
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                tqdm.write(f"Could not parse existing JSON file: {json_file}")
        
        # Remove old banner_results key if it exists
        if "banner_results" in existing_data:
            del existing_data["banner_results"]
            self._log(f"Removed old 'banner_results' data from {json_file}")
        
        # Update banner analysis data
        existing_data["banner_analysis"] = results
        
        # Write updated data
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2)
        
        self._log(f"Updated banner analysis for {domain} with extension {extension_folder}")

    def create_evaluation_dataset(self, output_dir="banner_system_eval/evaluation_data", nr_domains=None, extensions_to_evaluate=None):
        """Create evaluation dataset by processing specified domains and extensions."""
        os.makedirs(output_dir, exist_ok=True)
        
        stats = {
            "total_domains": 0,
            "domains_processed": 0,
            "screenshots_processed": 0,
            "extensions_evaluated": [], 
            "conclusions": { "removed": 0, "likely_removed": 0, "not_removed": 0, "unknown": 0, "not_loaded": 0 }
        }
        
        all_domains = self.get_domains_to_analyze(nr_domains=nr_domains)
        stats["total_domains"] = len(all_domains)
        
        if not all_domains:
            print("No domains found to process.")
            return stats

        # *** START CHANGE: Standardize the requested list ***
        standardized_extensions_to_evaluate = None
        if extensions_to_evaluate:
            standardized_extensions_to_evaluate = []
            for ext in extensions_to_evaluate:
                if ext == 'no_extensions':
                    standardized_extensions_to_evaluate.append('no_extension')
                else:
                    standardized_extensions_to_evaluate.append(ext)
            # Remove duplicates if both were somehow requested
            standardized_extensions_to_evaluate = list(set(standardized_extensions_to_evaluate)) 
            stats["extensions_evaluated"] = list(standardized_extensions_to_evaluate) # Use standardized list for stats
        # *** END CHANGE ***

        # Process each domain
        for domain in tqdm(all_domains, desc="Processing domains for evaluation"):
            domain_output_dir = os.path.join(output_dir, domain)

            domain_results = self.analyze_domain(domain) 
            
            if not domain_results:
                tqdm.write(f"Warning: No analysis results found for domain {domain}, skipping.")
                continue

            # Standardize 'no_extensions' key in results (keep this)
            if 'no_extensions' in domain_results and 'no_extension' not in domain_results:
                domain_results['no_extension'] = domain_results.pop('no_extensions')
                
            os.makedirs(domain_output_dir, exist_ok=True) 
            stats["domains_processed"] += 1

            extensions_in_results = list(domain_results.keys()) 
            
            # Filter based on STANDARDIZED user request OR use all available
            if standardized_extensions_to_evaluate: # Use the standardized list here
                process_extensions = [ext for ext in standardized_extensions_to_evaluate if ext in extensions_in_results]
            else:
                process_extensions = extensions_in_results 
                if not stats["extensions_evaluated"]: 
                     # Populate stats with standardized names if processing all
                     current_standardized_results = [k if k != 'no_extensions' else 'no_extension' for k in extensions_in_results]
                     stats["extensions_evaluated"] = list(set(stats["extensions_evaluated"] + current_standardized_results))


            if not process_extensions:
                 tqdm.write(f"Warning: No extensions to process for domain {domain} after filtering.")
                 continue

            # Create evaluation data for each relevant extension
            for ext_key in process_extensions:
                if ext_key in domain_results: 
                     if not domain_results[ext_key]:
                         tqdm.write(f"Warning: Domain {domain} - Results dictionary for '{ext_key}' is empty, skipping _create_extension_evaluation.")
                         continue

                     self._create_extension_evaluation(
                         domain=domain,
                         ext_key=ext_key, # Pass the standardized key ('no_extension')
                         ext_results=domain_results[ext_key], 
                         output_dir=domain_output_dir, 
                         stats=stats
                     )
                else:
                     tqdm.write(f"Error: Results for extension '{ext_key}' were expected but not found in domain_results for {domain}.")

        # ... (saving stats remains the same) ...
        # Save stats to a JSON file
        stats_file = os.path.join(output_dir, "evaluation_stats.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        print(f"\nEvaluation complete. Stats saved to {stats_file}")
        
        return stats

    def _create_extension_evaluation(self, domain, ext_key, ext_results, output_dir, stats):
        """
        Create evaluation data for a single extension on a domain
        
        Args:
            domain: Domain name
            ext_key: Extension key
            ext_results: Results for this extension
            output_dir: Where to save evaluation data
            stats: Statistics dictionary to update
        """
        # Create extension directory
        ext_dir = os.path.join(output_dir, ext_key)
        os.makedirs(ext_dir, exist_ok=True)
        
        # Get source screenshots
        screenshot_dir = os.path.join(self.banner_data_dir, "screenshots", domain)
        if not os.path.exists(screenshot_dir):
            return
        
        # Create an overview file for this extension
        overview_data = {
            "domain": domain,
            "extension": ext_key,
            "summary_status": ext_results.get("summary_status", "unknown"),
            "summary_reason": ext_results.get("summary_reason", []),
            "visits": {}
        }
        
        # Increment conclusion counter
        summary_status = ext_results.get("summary_status", "unknown")
        if summary_status in stats["conclusions"]:
            stats["conclusions"][summary_status] += 1
        
        # Process each visit
        for key, visit_data in ext_results.items():
            # Skip non-visit keys
            if key in ["summary_status", "summary_reason"]:
                continue
            
            visit_id = key  # e.g., "visit1"
            
            # Add to overview
            overview_data["visits"][visit_id] = {
                "conclusion": visit_data.get("conclusion", "unknown"),
                "reason": visit_data.get("reason", []),
                "page_loaded": visit_data.get("page_loaded", False),
                "page_status": visit_data.get("page_status", "unknown"),
                "html": visit_data.get("html", "unknown"),
                "screenshot": visit_data.get("screenshot", "unknown")
            }
            
            # Find all screenshots for this visit and extension
            visit_screenshots = []
            source_files = os.listdir(screenshot_dir)

            for filename in source_files:
                # Make sure this is for the current visit ID
                if not filename.startswith(visit_id): # More robust check than 'in'
                    continue
                
                filename_lower = filename.lower()
                
                # For no_extension folder, only include no_extension screenshots
                if ext_key == "no_extension":
                    if "_no_extension" in filename_lower and filename_lower.endswith(".png"): 
                        visit_screenshots.append(filename)
                    
                # For actual extensions, only include screenshots for that specific extension
                else:
                    # Construct the expected ending pattern, e.g., "_accept_all_cookies.png"
                    expected_ending = f"_{ext_key.lower()}.png" 
                    
                    # Check if the filename ends with the specific extension pattern 
                    # AND it's NOT a no_extension file
                    if filename_lower.endswith(expected_ending) and "_no_extension" not in filename_lower:
                        visit_screenshots.append(filename)

            # Copy and annotate screenshots
            for screenshot_file in visit_screenshots:
                src_path = os.path.join(screenshot_dir, screenshot_file)
                
                # Create a descriptive filename
                conclusion = visit_data.get("conclusion", "unknown")
                base_name = os.path.splitext(screenshot_file)[0]
                new_filename = f"{base_name}_{conclusion}{os.path.splitext(screenshot_file)[1]}"
                
                # Create destination path
                dst_path = os.path.join(ext_dir, new_filename)
                
                # Read the image
                try:
                    img = cv2.imread(src_path)
                    if img is None:
                        continue
                    
                    # Get original image dimensions
                    height, width = img.shape[:2]
                    
                    # Create a wider canvas with white background
                    # Add 400 pixels of width for the text area
                    text_width = 400
                    composite_width = width + text_width
                    composite_img = np.ones((height, composite_width, 3), dtype=np.uint8) * 255
                    
                    # Copy the original image to the left side
                    composite_img[0:height, 0:width] = img
                    
                    # Create text for annotation
                    annotation_text = [
                        f"Domain: {domain}",
                        f"Extension: {ext_key}",
                        f"Visit: {visit_id}",
                        f"Conclusion: {conclusion}",
                        f"Page Loaded: {visit_data.get('page_loaded', False)}",
                        f"Page Status: {visit_data.get('page_status', 'unknown')}",
                        f"HTML Analysis: {visit_data.get('html', 'unknown')}",
                        f"Screenshot Analysis: {visit_data.get('screenshot', 'unknown')}"
                    ]
                    
                    # Add reason information if available
                    reasons = visit_data.get("reason", [])
                    if reasons:
                        annotation_text.append(f"Reason: {reasons[0]}")
                        for additional_reason in reasons[1:]:
                            annotation_text.append(f"        {additional_reason}")
                    
                    # Add text to image on the right side
                    y_pos = 30
                    for line in annotation_text:
                        cv2.putText(composite_img, line, (width + 10, y_pos), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
                        y_pos += 25
                    
                    # Add a vertical line separating the image and text
                    cv2.line(composite_img, (width, 0), (width, height), (0, 0, 0), 2)
                    
                    # Save annotated image
                    result = cv2.imwrite(dst_path, composite_img)
                    
                    stats["screenshots_processed"] += 1
                    
                except Exception as e:
                    import traceback
                    tqdm.write(f"Error processing image {src_path}: {str(e)}")
                    tqdm.write(traceback.format_exc())
        
        # Save overview data
        overview_path = os.path.join(ext_dir, f"{domain}_overview.json")
        with open(overview_path, "w") as f:
            json.dump(overview_data, f, indent=2)

if __name__ == "__main__":
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
    
    def test_single_extension():
        # Single extension test code
        analyzer = BannerAnalyzer(banner_data_dir="data/Varies runs/banner_data_trial02", 
                                crawler_data_dir="data/Varies runs/crawler_data_trial02",
                                verbose=True)
    
        # Choose a domain and extension to test
        test_domain = "sap.com"  # Replace with an actual domain in your dataset
        test_extension = "consent_o_matic_opt_in"
        
        # Run the single extension test
        results = analyzer.analyze_single_extension(
            domain=test_domain,
            extension_name=test_extension,
            test_run=True
        )
    
        tqdm.write("\nTest completed")
    
    #test_single_extension()

    def evaluate_banners():
        # Evaluation Run
        # 1. Create the analyzer
        analyzer = BannerAnalyzer(banner_data_dir="data/Varies runs/banner_data_trial02", 
                                crawler_data_dir="data/Varies runs/crawler_data_trial02",
                                verbose=True)
    
        # 2. Create evaluation dataset
        stats = analyzer.create_evaluation_dataset(
            output_dir="evaluation_data",
            nr_domains=100,
            extensions_to_evaluate=["no_extensions", "consent_o_matic_opt_in", "adguard"]
        )
                
        tqdm.write("\nEvaluation stats:")
        tqdm.write(json.dumps(stats, indent=2))

    evaluate_banners()