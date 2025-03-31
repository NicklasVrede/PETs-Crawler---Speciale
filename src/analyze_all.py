import os
import multiprocessing
from tqdm import tqdm
from analyzers.source_identifier import SourceIdentifier
from analyzers.cookie_classifier import CookieClassifier
from analyzers.add_domain_categories import add_categories_to_files
from analyzers.banner_analyzer import BannerAnalyzer

def process_all_crawler_data():
    """Process all folders in crawler_data using all analyzers"""
    base_dir = os.path.join('data', 'crawler_data')
    
    # Get all folders in crawler_data
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        print("No folders found in data/crawler_data")
        return
        
    print(f"Found {len(folders)} folders to process")
    
    # Create instances of analyzers
    source_identifier = SourceIdentifier()
    cookie_classifier = CookieClassifier(verbose=False)
    
    if False:
        # Process each folder with progress bar
        for folder in tqdm(folders, desc="Processing folders", unit="folder"):
            folder_path = os.path.join(base_dir, folder)
        
        # First run identify_sources
        source_identifier.identify_site_sources(folder_path)
        
        # Then run cookie_classifier
        cookie_classifier.classify_directory(folder_path)
        
        # Add domain categories
        add_categories_to_files(folder_path)
    
    # Run banner analysis as the final step (processes all folders at once)
    print("\nRunning banner analysis...")
    banner_analyzer = BannerAnalyzer(
        banner_data_dir="data/banner_data",
        crawler_data_dir=base_dir
    )
    
    # Run the banner analysis
    banner_analyzer.analyze_all_banners(
        test_run=False,            
        test_domain=None,
        test_count=None,
        use_parallel=8,    
        max_workers=None
    )
    
    print("\nAll analyses completed!")

if __name__ == "__main__":
    process_all_crawler_data() 