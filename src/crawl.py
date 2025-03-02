import asyncio
from crawler.page_crawler import WebsiteCrawler
from managers.site_manager import SiteManager
import json
from pathlib import Path
import os
from util import construct_paths, extract_javascript, load_config, get_profile_config
from identify_sources import identify_site_sources



async def main(setup, storage_name, data_dir=None):
    # Load configuration
    config = load_config('config.json')
    
    # Extract profile configuration
    profile_config = get_profile_config(config, setup)
    
    # Construct paths
    user_data_dir, full_extension_path = construct_paths(config, setup)
    
    #debugging:
    #print(f"Using data directory: {user_data_dir}")
    #print(f"Using extension path: {full_extension_path}")

    site_manager = SiteManager(storage_name)
    rank, domain = site_manager.get_next_site()
    
    # Crawl site
    crawler = WebsiteCrawler(max_pages=20)
    site_data = await crawler.crawl_site(
        domain,
        user_data_dir=user_data_dir,
        full_extension_path=full_extension_path,
        headless=profile_config.get('headless', False),
        viewport=profile_config.get('viewport', {'width': 1280, 'height': 800})
    )
    
    # Debug print
    print(f"\nDebug: Total requests captured: {len(crawler.network_monitor.requests)}")
    
    # Store data
    site_manager.save_site_data(
        domain, 
        rank, 
        crawler.network_monitor,
        fingerprinting_data=site_data['fingerprinting']
    )
    
    # Extract JavaScript from the saved data
    json_file = site_manager.get_site_data_file(domain)
    #extract_javascript(json_file)

if __name__ == "__main__":
    #available profiles
    config = load_config('config.json')
    profile_names = config.get('profiles', {}).keys()
    print("Profile names:", list(profile_names))

    current_profile = 'consent_o_matic_opt_out'
    storage_name = f"{current_profile}_non_headless"
    asyncio.run(main(current_profile, storage_name))

    #Run the identify_sources script
    #identify_site_sources("data/adguard_non_headless")
    