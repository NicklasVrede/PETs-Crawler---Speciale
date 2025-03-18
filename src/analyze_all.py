import os
from tqdm import tqdm
from identify_sources import identify_site_sources
from cookie_classifier import classify_site_cookies

def process_all_crawler_data():
    """Process all folders in crawler_data using both analyzers"""
    base_dir = os.path.join('data', 'crawler_data')
    
    # Get all folders in crawler_data
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        print("No folders found in data/crawler_data")
        return
        
    print(f"Found {len(folders)} folders to process")
    
    # Process each folder
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        print(f"\nProcessing folder: {folder}")
        
        # First run identify_sources
        print("\nIdentifying sources...")
        identify_site_sources(folder_path)
        
        # Then run cookie_classifier
        print("\nClassifying cookies...")
        classify_site_cookies(folder_path)
        
        print(f"✓ Completed processing {folder}")

if __name__ == "__main__":
    process_all_crawler_data() 