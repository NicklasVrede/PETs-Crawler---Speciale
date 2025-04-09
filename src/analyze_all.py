import os
from tqdm import tqdm
import multiprocessing
from functools import partial
from analyzers.source_identifier import SourceIdentifier
from analyzers.cookie_classifier import CookieClassifier
from analyzers.add_domain_categories import add_categories_to_files
from analyzers.banner_analyzer import BannerAnalyzer
from analyzers.analyze_persistence import StorageAnalyzer

def process_folder(folder_path):
    """Process a single folder with all analyzers"""
    # Create instances of analyzers for this process
    source_identifier = SourceIdentifier()
    storage_analyzer = StorageAnalyzer()
    
    # Run identify_sources
    source_identifier.identify_site_sources(folder_path)
    
    # Add domain categories
    add_categories_to_files(folder_path)
    
    # Run persistence analysis
    storage_analyzer.analyze_directory(folder_path)
    
    return folder_path

def run_cookie_classification_sequentially(folders, base_dir):
    """Run cookie classification one folder at a time sequentially"""
    cookie_classifier = CookieClassifier()
    print("\nRunning cookie classification sequentially for all folders...")
    for folder in tqdm(folders, desc="Cookie classification", unit="folder"):
        folder_path = os.path.join(base_dir, folder)
        cookie_classifier.classify_directory(folder_path)

def process_all_crawler_data(test=False, num_workers=None):
    """Process crawler data using all analyzers
    Args:
        test (bool): If True, only process the 'test' folder
        num_workers (int): Number of parallel workers to use. If None, uses CPU count - 1
    """
    base_dir = os.path.join('data', 'crawler_data non-kameleo')
    
    if test:
        # Only process the test folder
        folders = ['test']
        print(f"TEST MODE: Only processing the 'test' folder")
        
        # Check if test folder exists
        if not os.path.isdir(os.path.join(base_dir, 'test')):
            print(f"Test folder not found at {os.path.join(base_dir, 'test')}")
            return
    else:
        # Get all folders in crawler_data
        folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
        
        if not folders:
            print("No folders found in data/crawler_data non-kameleo")
            return
        
        print(f"Found {len(folders)} folders to process")
    
    if len(folders) == 0:
        print("No folders to process")
        return
    
    # Process the first folder sequentially to warm up caches
    first_folder = folders[0]
    first_folder_path = os.path.join(base_dir, first_folder)
    print(f"\nProcessing first folder sequentially to warm up caches: {first_folder}")
    process_folder(first_folder_path)
    
    # Process remaining folders in parallel if there are any
    remaining_folders = folders[1:]
    if remaining_folders and not test:
        # Set up number of workers
        if num_workers is None:
            num_workers = max(1, multiprocessing.cpu_count() - 1)
        
        print(f"\nProcessing {len(remaining_folders)} remaining folders in parallel with {num_workers} workers")
        
        # Create a list of full paths for remaining folders
        folder_paths = [os.path.join(base_dir, folder) for folder in remaining_folders]
        
        # Process folders in parallel
        with multiprocessing.Pool(num_workers) as pool:
            # Use tqdm to show progress
            for _ in tqdm(
                pool.imap_unordered(process_folder, folder_paths),
                total=len(folder_paths),
                desc="Processing folders",
                unit="folder"
            ):
                pass
    
    # Run cookie classification sequentially for all folders
    print("\nRunning cookie classification sequentially for all folders...")
    run_cookie_classification_sequentially(folders, base_dir)
    
    # Run banner analysis as the final step (already multi-processed)
    print("\nRunning banner analysis...")
    banner_analyzer = BannerAnalyzer(
        banner_data_dir="data/banner_data non-kameleo",
        crawler_data_dir=base_dir
    )
    
    if not test:
        # Run the banner analysis
        banner_analyzer.analyze_all_banners(
            test_run=False,            
            test_domain=None,
            test_count=None,
            use_parallel=8,    
            max_workers=None
        )
    
    print(f"\n{'Test' if test else 'All'} analyses completed!")

if __name__ == "__main__":
    # You can specify the number of workers by uncommenting the next line
    # process_all_crawler_data(num_workers=4)
    process_all_crawler_data() 