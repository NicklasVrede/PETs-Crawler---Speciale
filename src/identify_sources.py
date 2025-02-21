import os
import json
from datetime import datetime
import sys
from tqdm import tqdm
sys.path.append('.')
from managers.ghostery_manager import GhosteryManager

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

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
                'identified_sources': []
            }
            
            # Get total number of requests for progress bar
            total_requests = sum(len(page.get('requests', [])) for page in site_data['pages'].values())
            
            # Analyze each request in the site data with nested progress bar
            with tqdm(total=total_requests, desc=f"Analyzing {filename}", leave=False) as pbar:
                for page_data in site_data['pages'].values():
                    for request in page_data.get('requests', []):
                        result = analyzer.analyze_request(request['url'])
                        pbar.update(1)
                        
                        if result['is_tracker']:  # Will update this in GhosteryManager later
                            source_analysis['total_analyzed'] += 1
                            
                            # Update category stats
                            if result['category']:
                                source_analysis['source_categories'][result['category']] = \
                                    source_analysis['source_categories'].get(result['category'], 0) + 1
                            
                            # Update organization stats
                            if result['organization']:
                                source_analysis['source_owners'][result['organization']] = \
                                    source_analysis['source_owners'].get(result['organization'], 0) + 1
                            
                            # Store detailed resource info
                            source_analysis['identified_sources'].append({
                                'url': request['url'],
                                'resource_type': result['pattern_name'],
                                'category': result['category'],
                                'organization': result['organization'],
                                'details': result.get('details', {})
                            })
            
            # Add analysis to site data
            site_data['source_analysis'] = source_analysis
            site_data['last_analyzed'] = datetime.now()
            
            # Save updated data
            save_json(site_data, file_path)
            
            # Print summary
            tqdm.write(f"\nResults for {site_data.get('domain', filename)}:")
            tqdm.write(f"Total analyzed requests: {source_analysis['total_analyzed']}")
            tqdm.write("Source categories:")
            for category, count in source_analysis['source_categories'].items():
                tqdm.write(f"  - {category}: {count}")
            tqdm.write("Source owners:")
            for org, count in source_analysis['source_owners'].items():
                tqdm.write(f"  - {org}: {count}")
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")

if __name__ == "__main__":
    identify_site_sources() 