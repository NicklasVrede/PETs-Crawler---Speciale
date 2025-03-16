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

    def save_crawl_data(self, domain, rank, network_monitor, fingerprint_collector, verbose=False):
        site_data = {
            'domain': domain,
            'rank': rank,
            'timestamp': datetime.now(),
            'network_data': network_monitor.get_network_data(),
            'statistics': network_monitor.get_statistics(),
            'cookies': network_monitor.get_cookies(),
            'storage': network_monitor.get_storage_data(),
            'fingerprinting': fingerprint_collector.get_fingerprinting_data()
        }
        
        crawler_data_dir = os.path.join('data', 'crawler_data', self.storage_folder)
        os.makedirs(crawler_data_dir, exist_ok=True)
        
        json_path = os.path.join(crawler_data_dir, f'{domain}.json')
        self._save_to_json(site_data, json_path, verbose)
        
        # Print final statistics only if verbose
        if verbose:
            stats = site_data['statistics']
            print(f"\nNetwork Statistics:")
            print(f"Total Requests: {stats['total_requests']}")
            print(f"Request Types: {stats['request_types']}")
            
            if site_data['fingerprinting']:
                print("\nFingerprinting Statistics:")
                summary = site_data['fingerprinting']['summary']
                if summary.get('fingerprinting_detected'):
                    print(f"Fingerprinting detected: Yes")
                    print(f"Techniques detected: {', '.join(summary['techniques_detected'])}")
                    print(f"Total API calls: {summary['summary']['total_calls']}")
                    print(f"Pages analyzed: {summary['summary']['pages_analyzed']}")
                    print(f"Category breakdown: {dict(summary['summary']['category_counts'])}")
                    print(f"\nVisits: {len(summary['visit_summaries'])}")
                    for visit in summary['visit_summaries']:
                        print(f"  Visit #{visit['visit_number']}: {visit['total_calls']} calls")
                else:
                    print("No fingerprinting detected")

    def get_result_file_path(self, domain):
        """Get the full path to a site's crawl result file"""
        return f"data/crawler_data/{self.storage_folder}/{domain}.json"