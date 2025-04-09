import asyncio
import os
import shutil
from crawler.page_crawler_kameleo import WebsiteCrawler, KameleoLocalApiClient
from managers.crawl_data_manager import CrawlDataManager
from utils.util import (construct_paths, load_config, get_profile_config, 
                       get_all_sites, create_temp_profile_copy)
from tqdm import tqdm
from pprint import pprint
import requests


def get_profiles_ids():
    kameleo_port = 5050
    profiles_url = f"http://localhost:{kameleo_port}/profiles"
    response = requests.get(profiles_url)

    ids = [profile['id'] for profile in response.json()]
    names = [profile['name'] for profile in response.json()]
    
    return dict(zip(names, ids))


async def crawl_domain(profile_name, profile_id, site_info, data_dir=None, 
                       subpages_nr=2, verbose=False, skip_existence_check=False, 
                       kameleo_client=None, extension_name=None):
    """
    Crawl a single domain with configurable verbosity
    
    Args:
        profile: Browser profile to use
        site_info: Tuple of (rank, domain)
        data_dir: Custom data directory (for parallel processing)
        max_pages: Maximum pages to crawl
        verbose: If True, print detailed progress information
        skip_existence_check: If True, skip checking if data already exists
    """
    # Load configuration
    config = load_config('config.json')    
    # Extract profile configuration
    profile_config = get_profile_config(config, profile_name)

    # Construct paths
    user_data_dir, full_extension_path = construct_paths(config, profile_name)
    
    # Use provided data_dir if specified, otherwise use the temp profile
    crawl_user_data_dir = data_dir

    crawl_data_manager = CrawlDataManager(profile_name)
    rank, domain = site_info
    
    # Crawl site
    crawler = WebsiteCrawler(
        domain=domain,
        profile_name=profile_name,
        profile_id=profile_id,
        subpages_nr=subpages_nr,
        visits=2,
        verbose=verbose,
        kameleo_client=kameleo_client,
        extension_name=extension_name
    )
    
    
    result = await crawler.crawl_site(
        domain,
        user_data_dir=crawl_user_data_dir,
    )
    
    # Store data
    if verbose:
        print(f"Saving data for domain {domain}...")
    
    target_dir = os.path.join('data', 'crawler_data', profile_name)
    os.makedirs(target_dir, exist_ok=True)
    
    crawl_data_manager.save_crawl_data(domain, rank, result, verbose=verbose)
        


if __name__ == "__main__":
    
    profiles_ids = get_profiles_ids()

    #pprint(profiles_ids)

    profile_name = 'disconnect'
    profile_id = profiles_ids[profile_name]

    all_sites = get_all_sites()

    site_info = all_sites[0]
    rank, domain = site_info

    # Create a single Kameleo client to reuse
    kameleo_client = KameleoLocalApiClient(url_endpoint="http://localhost:5050")

    asyncio.run(crawl_domain(profile_name, profile_id, site_info, verbose=False, kameleo_client=kameleo_client, extension_name=profile_name))
