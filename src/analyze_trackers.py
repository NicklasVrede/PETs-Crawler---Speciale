import os
import json
from datetime import datetime
import sys

# Debug: Print current working directory and check file existence
print("Current working directory:", os.getcwd())
print("Contents of current directory:", os.listdir())

if os.path.exists('data'):
    print("\nContents of data directory:", os.listdir('data'))
    if os.path.exists('data/baseline'):
        print("\nContents of baseline directory:", os.listdir('data/baseline'))
else:
    print("'data' directory not found")

sys.path.append('.')  # Add current directory to path
from managers.ghostery_manager import GhosteryManager

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

def analyze_site_files():
    """Analyze all site JSON files in the data directory for tracking behavior"""
    analyzer = GhosteryManager()
    
    # Get the absolute path to the baseline directory
    current_dir = os.getcwd()
    data_dir = os.path.join(current_dir, 'data', 'baseline')
    
    print(f"Looking for files in: {data_dir}")
    
    # Process each JSON file in the directory
    for filename in os.listdir(data_dir):
        if not filename.endswith('.json'):
            continue
            
        file_path = os.path.join(data_dir, filename)
        print(f"\nAnalyzing {filename}...")
        print(f"Full path: {file_path}")  # Debug print
        
        try:
            # Load existing data
            site_data = load_json(file_path)
            
            # Initialize tracking stats
            tracking_stats = {
                'total_tracked': 0,
                'categories': {},
                'organizations': {},
                'trackers': []
            }
            
            # Analyze each request in the site data
            for page_data in site_data['pages'].values():
                for request in page_data.get('requests', []):
                    result = analyzer.analyze_request(request['url'])
                    
                    if result['is_tracker']:
                        tracking_stats['total_tracked'] += 1
                        
                        # Update category stats
                        if result['category']:
                            tracking_stats['categories'][result['category']] = \
                                tracking_stats['categories'].get(result['category'], 0) + 1
                        
                        # Update organization stats
                        if result['organization']:
                            tracking_stats['organizations'][result['organization']] = \
                                tracking_stats['organizations'].get(result['organization'], 0) + 1
                        
                        # Store detailed tracker info
                        tracking_stats['trackers'].append({
                            'url': request['url'],
                            'pattern_name': result['pattern_name'],
                            'category': result['category'],
                            'organization': result['organization'],
                            'details': result.get('details', {})
                        })
            
            # Add tracking analysis to site data
            site_data['tracking'] = tracking_stats
            site_data['last_analyzed'] = datetime.now()
            
            # Save updated data
            save_json(site_data, file_path)
            
            # Print summary
            print(f"Results for {site_data.get('domain', filename)}:")
            print(f"Total tracked requests: {tracking_stats['total_tracked']}")
            print("Categories detected:")
            for category, count in tracking_stats['categories'].items():
                print(f"  - {category}: {count}")
            print("Organizations detected:")
            for org, count in tracking_stats['organizations'].items():
                print(f"  - {org}: {count}")
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            import traceback
            traceback.print_exc()  # This will print the full error trace

if __name__ == "__main__":
    analyze_site_files() 