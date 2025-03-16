import asyncio
import os
import shutil
from crawler.page_crawler import WebsiteCrawler
from managers.crawl_data_manager import CrawlDataManager
from utils.util import (construct_paths, load_config, get_profile_config, 
                       get_all_sites, create_temp_profile_copy)
from tqdm import tqdm


async def crawl_domain(profile, site_info, data_dir=None, max_pages=2, verbose=False):
    """
    Crawl a single domain with configurable verbosity
    
    Args:
        profile: Browser profile to use
        site_info: Tuple of (rank, domain)
        data_dir: Custom data directory (for parallel processing)
        max_pages: Maximum pages to crawl
        verbose: If True, print detailed progress information
    """
    # Load configuration
    config = load_config('config.json')
    
    # Extract profile configuration
    profile_config = get_profile_config(config, profile)
    
    # Construct paths
    user_data_dir, full_extension_path = construct_paths(config, profile)
    
    # Create a temporary copy of the profile for parallel execution
    temp_profile_dir = None
    try:
        # Use the utility function to create a temporary profile copy
        temp_profile_dir = create_temp_profile_copy(user_data_dir, verbose)
        
        # Use provided data_dir if specified, otherwise use the temp profile
        crawl_user_data_dir = data_dir if data_dir else temp_profile_dir
        
        if verbose:
            print(f"Using extension path: {full_extension_path}")
            print(f"Using profile data directory: {crawl_user_data_dir}")
        
        crawl_data_manager = CrawlDataManager(profile)
        rank, domain = site_info
        
        # Crawl site - pass verbose flag to control internal printing
        crawler = WebsiteCrawler(max_pages=max_pages, verbose=verbose)
        result = await crawler.crawl_site(
            domain,
            user_data_dir=crawl_user_data_dir,
            full_extension_path=full_extension_path,
            headless=profile_config.get('headless', False),
            viewport=profile_config.get('viewport', {'width': 1280, 'height': 800})
        )
        
        # Store data
        if verbose:
            print(f"Saving data for domain {domain}...")
        
        target_dir = os.path.join('data', 'crawler_data', profile)
        os.makedirs(target_dir, exist_ok=True)
        
        crawl_data_manager.save_crawl_data(domain, rank, result, verbose=verbose)
        
        # Always show file saved confirmation, even in non-verbose mode
        expected_file = os.path.join(target_dir, f'{domain}.json')
        if os.path.exists(expected_file):
            file_size = os.path.getsize(expected_file) / 1024
            tqdm.write(f"✓ Data saved: {expected_file} ({file_size:.2f} KB)")
        else:
            tqdm.write(f"✗ File not found: {expected_file}")
            
    finally:
        # Clean up temporary directory
        if temp_profile_dir and os.path.exists(temp_profile_dir):
            if verbose:
                print(f"Cleaning up temporary profile directory: {temp_profile_dir}")
            shutil.rmtree(temp_profile_dir, ignore_errors=True)


if __name__ == "__main__":
    #available profiles
    config = load_config('config.json')
    profile_names = config.get('profiles', {}).keys()
    print("Profile names:", list(profile_names))

    profile = 'i_dont_care_about_cookies'
    
    # Get all sites to crawl
    all_sites = get_all_sites()
    if all_sites:
        # Just process the first site for testing
        site_info = all_sites[0]  # Get only the first site
        rank, domain = site_info
        print(f"\n{'='*50}")
        print(f"Processing site: {domain} (rank: {rank})")
        print(f"{'='*50}\n")
        
        try:
            asyncio.run(crawl_domain(profile, site_info=site_info))
            print(f"Completed crawling {domain}")
        except Exception as e:
            print(f"Error crawling {domain}: {str(e)}")
    else:
        print("No sites available to crawl")

    #Run the identify_sources script
    #identify_site_sources("data/adguard_non_headless")
    