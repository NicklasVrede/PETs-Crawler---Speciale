import asyncio
from crawler.page_crawler import WebsiteCrawler
from managers.crawl_data_manager import CrawlDataManager
from utils.util import construct_paths, extract_javascript, load_config, get_profile_config



async def main(profile, data_dir=None):
    # Load configuration
    config = load_config('config.json')
    
    # Extract profile configuration
    profile_config = get_profile_config(config, profile)
    
    # Construct paths
    user_data_dir, full_extension_path = construct_paths(config, profile)
    
    #print the full extension path
    print(f"Using extension path: {full_extension_path}")

    #debugging:
    #print(f"Using data directory: {user_data_dir}")
    #print(f"Using extension path: {full_extension_path}")

    # Create SiteManager (no logs_folder parameter needed anymore)
    
    max_pages = 5

    crawl_data_manager = CrawlDataManager(profile)
    rank, domain = crawl_data_manager.get_next_site()
    
    # Crawl site
    crawler = WebsiteCrawler(max_pages=max_pages)
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
    crawl_data_manager.save_crawl_data(
        domain, 
        rank, 
        crawler.network_monitor,
        fingerprint_collector=crawler.fp_collector
    )
    
    # Extract JavaScript from the saved data
    json_file = crawl_data_manager.get_result_file_path(domain)
    #extract_javascript(json_file)

if __name__ == "__main__":
    #available profiles
    config = load_config('config.json')
    profile_names = config.get('profiles', {}).keys()
    print("Profile names:", list(profile_names))

    profile = 'i_dont_care_about_cookies'
    asyncio.run(main(profile))

    #Run the identify_sources script
    #identify_site_sources("data/adguard_non_headless")
    