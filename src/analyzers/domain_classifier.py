import csv
import time
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

class DomainClassifier:
    def __init__(self, csv_path="data/study-sites.csv", json_path="data/domain_categories.json"):
        self.csv_path = Path(csv_path)
        self.json_path = Path(json_path)
        self.domains = self._load_domains()
        self.classifications = self._load_existing_classifications()
        
    def _load_domains(self):
        """Load domains from CSV file."""
        domains = []
        with open(self.csv_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                domains.append(row['domain'])
        return domains
    
    def _load_existing_classifications(self):
        """Load existing classifications from JSON file if it exists."""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r') as file:
                    existing_data = json.load(file)
                    print(f"Loaded existing classifications for {len(existing_data)} domains from {self.json_path}")
                    return existing_data
            except Exception as e:
                print(f"Error loading existing classifications: {e}")
        
        print("No existing classifications found, starting fresh")
        return {}
    
    def _clean_categories(self, categories_text):
        """Clean categories and convert to a list.
        
        Converts "- Category1\n- Category2\n" to ["Category1", "Category2"]
        """
        categories = []
        
        # Split by newline and process each line
        for line in categories_text.split('\n'):
            # Remove the "- " prefix and strip whitespace
            line = line.strip()
            if line.startswith('- '):
                line = line[2:].strip()
            
            # Add non-empty categories to the list
            if line:
                categories.append(line)
                
        return categories
    
    def classify_domains(self, start_index=0, end_index=None, delay=2):
        """Classify domains using trustedsource.org."""
        if end_index is None:
            end_index = len(self.domains)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            for i, domain in enumerate(self.domains[start_index:end_index], start=start_index):
                # Skip if already classified
                if domain in self.classifications:
                    print(f"Skipping {domain}: already classified")
                    continue
                
                print(f"Processing {i+1}/{end_index}: {domain}")
                
                try:
                    # Navigate to trustedsource.org
                    page.goto("https://trustedsource.org/en/feedback/url?action=checksingle")
                    
                    # Fill the form
                    page.select_option('select[name="product"]', '01-ts')  # Select "Trellix Real-Time Database"
                    page.fill('input[name="url"]', f"http://{domain}")
                    
                    # Submit the form
                    page.click('input[type="submit"][value="Check URL"]')
                    
                    # Wait for results to load
                    page.wait_for_selector('.result-table')
                    
                    # Extract categories
                    categories_text = page.locator('tr[bgcolor="#ffffff"] td:nth-child(4)').inner_text()
                    
                    # Clean categories and convert to list
                    categories_list = self._clean_categories(categories_text)
                    
                    # Add to our classifications dictionary with domain as key
                    self.classifications[domain] = categories_list
                    
                    print(f"Classified {domain}: {categories_list}")
                    
                    # Save after each successful classification to preserve progress
                    self.export_to_json()
                    
                    # Wait to avoid rate limiting
                    time.sleep(delay)
                    
                except Exception as e:
                    print(f"Error processing {domain}: {e}")
                    continue
            
            browser.close()
    
    def export_to_json(self, output_path=None):
        """Export classifications to JSON."""
        if output_path is None:
            output_path = self.json_path
        
        # Write to JSON file
        with open(output_path, 'w') as file:
            json.dump(self.classifications, file, indent=4)
        
        print(f"Exported classifications for {len(self.classifications)} domains to {output_path}")

if __name__ == "__main__":
    # Make sure the data directory exists
    Path("data").mkdir(exist_ok=True)
    
    classifier = DomainClassifier()
    
    # Process all domains (you can adjust the range as needed)
    classifier.classify_domains()
    
    # Export the results to JSON (though this will already have been done)
    classifier.export_to_json()