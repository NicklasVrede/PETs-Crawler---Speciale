import os
import json
from datetime import datetime
import sys
from tqdm import tqdm
from urllib.parse import urlparse
from collections import Counter
sys.path.append('.')
from managers.ghostery_manager import GhosteryManager

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

def get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def identify_site_sources():
    """Identify the sources/origins of URLs in site data"""
    analyzer = GhosteryManager()
    
    # Get the absolute path to the baseline directory
    current_dir = os.getcwd()
    data_dir = os.path.join(current_dir, 'data', 'baseline')
    
    # Get list of JSON files
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    # Process each JSON file in the directory with progress bar
    for filename in tqdm(json_files, desc="Analyzing sites", unit="site"):
        file_path = os.path.join(data_dir, filename)
        
        try:
            # Load existing data
            site_data = load_json(file_path)
            
            # Initialize analysis stats
            source_analysis = {
                'total_analyzed': 0,
                'source_categories': {},
                'source_owners': {},
                'total_fingerprinting': 0,
                'fingerprinting_domains': [],
                'identified_sources': []
            }
            
            # Track unique base URLs and their request counts
            processed_urls = set()
            url_counts = Counter()
            
            # Count all URLs first
            for page_data in site_data['pages'].values():
                for request in page_data.get('requests', []):
                    base_url = get_base_url(request['url'])
                    url_counts[base_url] += 1
            
            # Get total number of requests for progress bar
            total_requests = sum(len(page_data.get('requests', [])) for page_data in site_data['pages'].values())
            
            # Analyze each request in the site data with nested progress bar
            with tqdm(total=total_requests, desc=f"Analyzing {filename}", leave=False) as pbar:
                for page_data in site_data['pages'].values():
                    for request in page_data.get('requests', []):
                        base_url = get_base_url(request['url'])
                        
                        # Skip if we've already processed this base URL
                        if base_url in processed_urls:
                            pbar.update(1)
                            continue
                            
                        processed_urls.add(base_url)
                        result = analyzer.analyze_request(base_url)
                        pbar.update(1)
                        
                        if result['fingerprinting']:
                            source_analysis['total_fingerprinting'] += 1
                            source_analysis['fingerprinting_domains'].append({
                                'url': base_url,
                                'request_count': url_counts[base_url],
                                'organization': result['organization'],
                                'category': result['category']
                            })
                        
                        if result['is_tracker']:
                            source_analysis['total_analyzed'] += 1
                            
                            # Update category stats
                            if result['category']:
                                source_analysis['source_categories'][result['category']] = \
                                    source_analysis['source_categories'].get(result['category'], 0) + 1
                            
                            # Update organization stats
                            if result['organization']:
                                source_analysis['source_owners'][result['organization']] = \
                                    source_analysis['source_owners'].get(result['organization'], 0) + 1
                            
                            # Store detailed resource info with base URL and request count
                            source_analysis['identified_sources'].append({
                                'url': base_url,
                                'request_count': url_counts[base_url],  # Add count of requests
                                'resource_type': result['pattern_name'],
                                'category': result['category'],
                                'organization': result['organization'],
                                'details': result.get('details', {})
                            })
            
            # Sort identified sources by request count (most frequent first)
            source_analysis['identified_sources'].sort(key=lambda x: x['request_count'], reverse=True)
            
            # Add analysis to site data
            site_data['source_analysis'] = source_analysis
            site_data['last_analyzed'] = datetime.now()
            
            # Save updated data
            save_json(site_data, file_path)
            
            # Print summary
            tqdm.write(f"\nResults for {site_data.get('domain', filename)}:")
            tqdm.write(f"Total analyzed requests: {source_analysis['total_analyzed']}")
            tqdm.write(f"Unique domains analyzed: {len(processed_urls)}")
            tqdm.write("\nTop 5 most frequent domains:")
            for source in source_analysis['identified_sources'][:5]:
                tqdm.write(f"  - {source['url']}: {source['request_count']} requests")
            tqdm.write("\nSource categories:")
            for category, count in source_analysis['source_categories'].items():
                tqdm.write(f"  - {category}: {count}")
            tqdm.write("Source owners:")
            for org, count in source_analysis['source_owners'].items():
                tqdm.write(f"  - {org}: {count}")
            tqdm.write(f"\nTotal fingerprinting domains: {source_analysis['total_fingerprinting']}")
            if source_analysis['fingerprinting_domains']:
                tqdm.write("\nFingerprinting domains:")
                for domain in source_analysis['fingerprinting_domains']:
                    tqdm.write(f"  - {domain['url']} ({domain['request_count']} requests)")
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")

if __name__ == "__main__":
    identify_site_sources() 