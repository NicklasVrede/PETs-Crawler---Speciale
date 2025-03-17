import asyncio
import os
import shutil
import json
import time
from pathlib import Path
from crawler.page_crawler import WebsiteCrawler
from managers.crawl_data_manager import CrawlDataManager
from utils.util import (construct_paths, load_config, get_profile_config, 
                       get_all_sites, create_temp_profile_copy)
from tqdm import tqdm


async def crawl_domain(profile, site_info, max_pages=2, verbose=False, show_progress=False, data_dir=None):
    """
    Crawl a single domain with configurable verbosity
    
    Args:
        profile: Browser profile to use
        site_info: Tuple of (rank, domain)
        max_pages: Maximum pages to crawl
        verbose: If True, print detailed progress information
        show_progress: Whether to show a progress bar for this domain
        data_dir: Directory to use for temporary profile data
    """
    # Load configuration
    config = load_config('config.json')
    
    # Extract profile configuration
    profile_config = get_profile_config(config, profile)
    
    # Construct paths to original profile and extension
    user_data_dir, full_extension_path = construct_paths(config, profile)
    
    rank, domain = site_info
    domain_safe = domain.lower().replace('.', '_')
    
    # Create a temporary profile directory without cleanup
    temp_base_dir = data_dir if data_dir else os.path.join("data", "temp_profiles") 
    os.makedirs(temp_base_dir, exist_ok=True)
    
    temp_profile_dir = os.path.join(temp_base_dir, f"profile_{domain_safe}")
    
    # Create the directory
    os.makedirs(temp_profile_dir, exist_ok=True)
    
    if verbose:
        print(f"Using temporary profile at: {temp_profile_dir}")
    
    # Copy only essential extension files instead of the whole profile
    try:
        # Create the Extensions directory
        ext_dir = os.path.join(temp_profile_dir, "Extensions")
        os.makedirs(ext_dir, exist_ok=True)
        
        # Copy the extension if it exists
        if full_extension_path and os.path.exists(full_extension_path):
            # Extract extension ID and version from path
            ext_parts = os.path.normpath(full_extension_path).split(os.sep)
            if len(ext_parts) >= 2:
                ext_id = ext_parts[-2]
                ext_version = ext_parts[-1]
                
                # Create destination path
                target_ext_path = os.path.join(ext_dir, ext_id, ext_version)
                os.makedirs(os.path.dirname(target_ext_path), exist_ok=True)
                
                # Copy extension files
                if os.path.isdir(full_extension_path):
                    shutil.copytree(full_extension_path, target_ext_path)
                
                if verbose:
                    print(f"Copied extension from {full_extension_path} to {target_ext_path}")
        
        crawl_data_manager = CrawlDataManager(profile)
        
        # Crawl site - pass verbose flag to control internal printing
        crawler = WebsiteCrawler(max_pages=max_pages, verbose=verbose, show_progress=show_progress)
        
        try:
            # Use the temporary profile directory instead of the original
            crawl_result = await crawler.crawl_site(
                domain,
                user_data_dir=temp_profile_dir,
                full_extension_path=full_extension_path,
                headless=profile_config.get('headless', False),
                viewport=profile_config.get('viewport', {'width': 1280, 'height': 800})
            )
            
            # Store data
            if verbose:
                print(f"Saving data for domain {domain}...")
            
            target_dir = os.path.join('data', 'crawler_data', profile)
            os.makedirs(target_dir, exist_ok=True)
            
            crawl_data_manager.save_crawl_data(
                domain, 
                rank, 
                crawl_result,
                verbose=verbose
            )
            
            return crawl_result
            
        except Exception as e:
            if verbose:
                print(f"Error crawling domain {domain}: {str(e)}")
            # Re-raise to let the caller handle it
            raise
    finally:
        # Clean up the temporary profile directory
        try:
            if os.path.exists(temp_profile_dir):
                shutil.rmtree(temp_profile_dir, ignore_errors=True)
                if verbose:
                    print(f"Cleaned up temporary profile: {temp_profile_dir}")
        except Exception as e:
            if verbose:
                print(f"Error cleaning up temp profile: {str(e)}")


if __name__ == "__main__":
    #available profiles
    config = load_config('config.json')
    profile_names = config.get('profiles', {}).keys()
    print("Profile names:", list(profile_names))

    profile = 'i_dont_care_about_cookies'
    
    verbose = False
    show_progress = False #bool for individual progress bar for domains.
    
    # Get all sites to crawl
    all_sites = get_all_sites()
    if all_sites:
        # Just process the first site for testing
        site_info = all_sites[0]  # Get only the first site
        rank, domain = site_info

        if verbose:
            print(f"\n{'='*50}")
            print(f"Processing site: {domain} (rank: {rank})")
            print(f"{'='*50}\n")
            
        try:
            asyncio.run(crawl_domain(profile, site_info=site_info, show_progress=True))
            print(f"Completed crawling {domain}")
        except Exception as e:
            print(f"Error crawling {domain}: {str(e)}")
    else:
        print("No sites available to crawl")

    #Run the identify_sources script
    #identify_site_sources("data/adguard_non_headless")
    