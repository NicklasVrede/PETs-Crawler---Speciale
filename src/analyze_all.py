import os
from tqdm import tqdm
from analyzers.source_identifier import SourceIdentifier
from analyzers.cookie_classifier import CookieClassifier
from analyzers.add_domain_categories import add_categories_to_files
from analyzers.banner_analyzer import BannerAnalyzer
from analyzers.analyze_persistence import StorageAnalyzer

def process_all_crawler_data(test=False):
    """Process crawler data using all analyzers
    Args:
        test (bool): If True, only process the 'test' folder
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
    
    # Create instances of analyzers
    source_identifier = SourceIdentifier()
    cookie_classifier = CookieClassifier()
    storage_analyzer = StorageAnalyzer()
    
    # Process each folder with progress bar
    for folder in tqdm(folders, desc="Processing folders", unit="folder"):
        folder_path = os.path.join(base_dir, folder)
    
        # First run identify_sources
        source_identifier.identify_site_sources(folder_path)
        
        # Then run cookie_classifier
        cookie_classifier.classify_directory(folder_path)
        
        # Add domain categories
        add_categories_to_files(folder_path)
        
        # Run persistence analysis
        storage_analyzer.analyze_directory(folder_path)
    
    # Run banner analysis as the final step (multi-processed)
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
    process_all_crawler_data(test=True) 