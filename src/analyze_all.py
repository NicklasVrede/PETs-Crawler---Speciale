import os
from tqdm import tqdm
from identify_sources import SourceIdentifier
from cookie_classifier import CookieClassifier
from add_domain_categories import add_categories_to_files

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
    

    # Process each folder with progress bar
    for folder in tqdm(folders, desc="Processing folders", unit="folder"):
        folder_path = os.path.join(base_dir, folder)
        
        # First run identify_sources
        source_identifier.identify_site_sources(folder_path)
        
        # Then run cookie_classifier
        cookie_classifier.classify_directory(folder_path)
        
        # Add domain categories
        add_categories_to_files(folder_path)

if __name__ == "__main__":
    process_all_crawler_data() 