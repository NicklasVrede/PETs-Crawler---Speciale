from datetime import datetime
import os
import json
import csv
from analyzers.cookie_analyzer import CookieAnalyzer
import tqdm

class CrawlDataManager:
    def __init__(self, storage_folder):
        self.storage_folder = storage_folder
        self.base_dir = os.path.join('data', 'crawler_data', self.storage_folder)

    def _save_to_json(self, data, filename, verbose=False):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        if verbose:
            print(f"Data saved to: {filename}")

    def save_crawl_data(self, domain, rank, crawl_result, verbose=False):
        """Save crawl data from a consolidated result object"""
        site_data = {
            'domain': domain,
            'rank': rank,
            'timestamp': datetime.now(),
            **crawl_result
        }
        
        crawler_data_dir = os.path.join('data', 'crawler_data', self.storage_folder)
        os.makedirs(crawler_data_dir, exist_ok=True)
        
        json_path = os.path.join(crawler_data_dir, f'{domain}.json')
        
        try:
            # Save the data
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(site_data, f, indent=2, default=str)
            
            # Report success with file size
            file_size = os.path.getsize(json_path) / 1024

            if verbose:
                tqdm.write(f"✓ Data saved: {json_path} ({file_size:.2f} KB)")
                self._print_statistics(site_data)
            
        except Exception as e:
            tqdm.write(f"✗ Error saving data to {json_path}: {str(e)}")

    def get_result_file_path(self, domain):
        """Get the full path to a site's crawl result file"""
        return f"data/crawler_data/{self.storage_folder}/{domain}.json"