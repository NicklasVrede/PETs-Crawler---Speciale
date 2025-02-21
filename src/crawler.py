import asyncio
from crawler.page_crawler import WebsiteCrawler
from managers.site_manager import SiteManager
import json
from pathlib import Path
import os

# Configuration
STORAGE_FOLDER = 'baseline'

def extract_javascript(json_file_path):
    """Extract JavaSc   ript from responses and add to dedicated scripts section"""
    #print(f"\nExtracting JavaScript from {json_file_path}")
    
    # Load JSON file
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    # Initialize scripts section if it doesn't exist
    if 'scripts' not in data:
        data['scripts'] = []
    
    # Process each request
    for page_data in data['pages'].values():
        for request in page_data.get('requests', []):
            if (request.get('resource_type') == 'script' and 
                'response' in request and 
                'body' in request['response'] and
                'content-type' in request['response']['headers'] and
                'javascript' in request['response']['headers']['content-type'].lower()):
                
                # Add to scripts section without beautifying
                script_data = {
                    'url': request['url'],
                    'page_url': request.get('page_url', 'unknown'),
                    'timestamp': request.get('timestamp', 'unknown'),
                    'content': request['response']['body']
                }
                
                data['scripts'].append(script_data)
                #print(f"Extracted script from {request['url']}")
    
    # Save updated JSON with scripts section
    with open(json_file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nExtracted {len(data['scripts'])} JavaScript files")

async def main():
    site_manager = SiteManager(STORAGE_FOLDER)
    rank, domain = site_manager.get_next_site()
    
    # Crawl site
    crawler = WebsiteCrawler(max_pages=20)
    urls = await crawler.crawl_site(domain)
    
    # Debug print
    print(f"\nDebug: Total requests captured: {len(crawler.network_monitor.requests)}")
    
    # Store data
    site_manager.save_site_data(domain, rank, crawler.network_monitor)
    
    # Extract JavaScript from the saved data
    json_file = site_manager.get_site_data_file(domain)
    extract_javascript(json_file)

if __name__ == "__main__":
    asyncio.run(main())