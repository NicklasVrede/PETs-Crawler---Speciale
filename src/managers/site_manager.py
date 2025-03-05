import os
import json
import csv
from datetime import datetime

class SiteManager:
    def __init__(self, storage_folder):
        self.storage_folder = storage_folder
        self.base_dir = os.path.join('data', self.storage_folder)
        self._ensure_directory_exists()

    def _ensure_directory_exists(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            print(f"Created directory: {self.base_dir}")

    def _save_to_json(self, data, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Data saved to: {filename}")

    def get_next_site(self):
        with open('data/study-sites.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            rank, domain = next(reader)
            return rank, domain

    def save_site_data(self, domain, rank, network_monitor, fingerprinting_data=None):
        site_data = {
            'domain': domain,
            'rank': rank,
            'timestamp': datetime.now(),
            'network_data': network_monitor.get_results(),
            'statistics': network_monitor.get_statistics(),
            'fingerprinting': fingerprinting_data
        }
        
        json_path = os.path.join(self.base_dir, f'{domain}.json')
        self._save_to_json(site_data, json_path)
        
        # Print final statistics
        stats = site_data['statistics']
        print(f"\nNetwork Statistics:")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Request Types: {stats['request_types']}")
        print(f"Total Cookies in Headers: {stats['total_cookies']}")
        
        if fingerprinting_data:
            print("\nFingerprinting Statistics:")
            if fingerprinting_data.get('techniques_detected'):
                print(f"Detected techniques: {', '.join(fingerprinting_data['techniques_detected'])}")
                print(f"Total API calls: {fingerprinting_data['summary']['total_calls']}")
            else:
                print("No fingerprinting techniques detected")

    def get_site_data_file(self, domain):
        """Get the full path to a site's JSON data file"""
        return f"data/{self.storage_folder}/{domain}.json" 