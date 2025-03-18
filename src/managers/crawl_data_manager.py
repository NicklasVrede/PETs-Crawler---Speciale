from datetime import datetime
import os
import json
import csv
from analyzers.cookie_analyzer import CookieAnalyzer

class CrawlDataManager:
    def __init__(self, storage_folder):
        self.storage_folder = storage_folder
        self.base_dir = os.path.join('data', 'crawler_data', self.storage_folder)

    def _save_to_json(self, data, filename, verbose=False):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        if verbose:
            print(f"Data saved to: {filename}")

    def save_crawl_data(self, domain, rank, site_data, verbose=False):
        crawler_data_dir = os.path.join('data', 'crawler_data', self.storage_folder)
        os.makedirs(crawler_data_dir, exist_ok=True)
        
        json_path = os.path.join(crawler_data_dir, f'{domain}.json')
        self._save_to_json(site_data, json_path, verbose)
        
        # Print stats if verbose
        if verbose:
            self._print_statistics(site_data)

    def get_result_file_path(self, domain):
        """Get the full path to a site's crawl result file"""
        return f"data/crawler_data/{self.storage_folder}/{domain}.json"