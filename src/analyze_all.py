import os
from tqdm import tqdm
from analyzers.source_identifier import SourceIdentifier
from analyzers.cookie_classifier import CookieClassifier
from analyzers.add_domain_categories import add_categories_to_files
from analyzers.banner_analyzer import BannerAnalyzer
from analyzers.analyze_persistence import StorageAnalyzer
import time


def process_all_crawler_data(base_dir=None, banner_data_dir=None):
    """Process all folders in crawler_data using all analyzers"""

    start_time = time.time()
    if base_dir is None:
        tqdm.write("No base directory provided, quitting")
        return

    # Get all folders in crawler_data
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        tqdm.write("No folders found in data/crawler_data")
        return
        
    tqdm.write(f"Found {len(folders)} folders to process")
    
    # Create instances of analyzers
    source_identifier = SourceIdentifier()
    cookie_classifier = CookieClassifier(verbose=False)
    storage_analyzer = StorageAnalyzer(verbose=False)

    # Process each folder with progress bar
    with tqdm(total=len(folders), desc="Processing folders", unit="folder") as progress_bar:
        for folder in folders:
            folder_path = os.path.join(base_dir, folder)
            
            # First run identify_sources
            progress_bar.set_description(f"Running source identification for {folder[:10]}...")
            source_identifier.identify_site_sources(folder_path)
            
            # Then run cookie_classifier
            progress_bar.set_description(f"Running cookie classification for {folder[:10]}...")
            cookie_classifier.classify_directory(folder_path)
            
            # Add domain categories
            progress_bar.set_description(f"Adding domain categories for {folder[:10]}...")
            add_categories_to_files(folder_path)

            # Run the storage analyzer
            progress_bar.set_description(f"Running storage analysis for {folder[:10]}...")
            storage_analyzer.analyze_directory(folder_path)
            
            # Update the progress bar after processing each folder
            progress_bar.update(1)
    
    # Run banner analysis as the final step (processes all folders at once)
    tqdm.write("Running banner analysis...")
    banner_analyzer = BannerAnalyzer(
        banner_data_dir=banner_data_dir,
        crawler_data_dir=base_dir
    )
    
    # Run the banner analysis
    banner_analyzer.analyze_all_banners(
        test_run=False,            
        test_domain=None,
        test_count=None,
        use_parallel=True,
        max_workers=None
    )
    
    elapsed_time = time.time() - start_time
    
    tqdm.write(f"All analyses completed! Time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    #Make sure to check directory paths
    process_all_crawler_data(base_dir="data/crawler_data", 
                             banner_data_dir="data/banner_data") 