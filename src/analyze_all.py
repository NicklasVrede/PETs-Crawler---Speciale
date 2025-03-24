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
    cookie_classifier = CookieClassifier()
    
    try:
        # Process each folder
        for folder in folders:
            folder_path = os.path.join(base_dir, folder)
            print(f"\nProcessing folder: {folder}")
            
            # First run identify_sources
            print("\nIdentifying sources...")
            source_identifier.identify_site_sources(folder_path)
            
            # Then run cookie_classifier
            print("\nClassifying cookies...")
            cookie_classifier.classify_directory(folder_path)
            
            # Add domain categories
            print("\nAdding domain categories...")
            add_categories_to_files(folder_path)
            
            print(f"✓ Completed processing {folder}")
    finally:
        # Make sure to close the classifier to free resources
        cookie_classifier.close()

if __name__ == "__main__":
    process_all_crawler_data() 