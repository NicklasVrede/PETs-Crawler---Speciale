import asyncio
import os
import random
from crawl_kameleo import crawl_domain, get_profiles_ids
from utils.util import load_config, get_all_sites, construct_paths
from tqdm import tqdm
from collections import defaultdict
from kameleo.local_api_client import KameleoLocalApiClient

# Create a single Kameleo client to reuse across all crawlers
kameleo_client = KameleoLocalApiClient(urls_endpoint="http://localhost:5050")

async def crawl_with_profile(config, profile_name, profile_id, sites, subpages_nr=2, verbose=False, overall_progress=None):
    """
    Crawl multiple sites with a single browser profile using Kameleo
    
    Args:
        config: Configuration dictionary
        profile_name: Browser profile name to use
        profile_id: Kameleo profile ID
        sites: List of (rank, domain) tuples to crawl
        subpages_nr: Number of subpages to crawl per site
        verbose: If True, print detailed progress information
        overall_progress: Overall progress bar to update
    """
    try:
        # Shuffle the sites list to randomize crawling order
        sites_to_crawl = sites.copy()  # Create a copy to avoid modifying the original
        random.shuffle(sites_to_crawl)
        
        if verbose:
            print(f"Shuffled {len(sites_to_crawl)} domains for random crawling order")
            
        # Crawl each site with this profile
        for site_info in sites_to_crawl:
            rank, domain = site_info
            try:
                if verbose:
                    print(f"Crawling {domain} with profile {profile_name}")
                        
                await crawl_domain(
                    profile_name=profile_name,
                    profile_id=profile_id,
                    site_info=site_info,
                    subpages_nr=subpages_nr,
                    verbose=verbose,
                    skip_existence_check=True,  # Skip the check since we've done it already
                    kameleo_client=kameleo_client,  # Pass the shared client
                    extension_name=profile_name
                )
                
                if verbose:
                    print(f"Completed crawl of {domain} with profile {profile_name}")
                
                # Update the overall progress bar if provided
                if overall_progress:
                    overall_progress.update(1)
                    
            except Exception as e:
                print(f"Error crawling {domain} with profile {profile_name}: {str(e)}")
    except Exception as e:
        print(f"Error in crawl_with_profile for {profile_name}: {str(e)}")

    tqdm.write(f"Crawl with profile {profile_name} completed, visiting {sites_to_crawl[0][1]}")

def precheck_existing_data(profiles, sites, verbose=False):
    """
    Pre-check which domain+extension combinations already have data and screenshots
    
    Args:
        profiles: List of profiles/extensions to check
        sites: List of (rank, domain) tuples to check
        verbose: Whether to print verbose output
        
    Returns:
        Dictionary mapping profile -> set of domains with existing data
    """
    if verbose:
        print("Pre-checking existing data files and screenshots...")
    
    # Create a dictionary to store results
    existing_data = defaultdict(set)
    base_dir = "data/crawler_data"
    screenshot_base_dir = "data/banner_data/screenshots"
    
    # Check each profile directory
    with tqdm(total=len(profiles), desc="Checking profiles", unit="profile") as pbar:
        for profile in profiles:
            profile_dir = os.path.join(base_dir, profile)
            if not os.path.exists(profile_dir):
                if verbose:
                    print(f"Profile directory {profile_dir} does not exist")
                pbar.update(1)
                continue
                
            # Check each domain
            with tqdm(total=len(sites), desc=f"Checking {profile}", unit="site", leave=False) as domain_pbar:
                for rank, domain in sites:
                    domain_file = os.path.join(profile_dir, f"{domain}.json")
                    
                    # Check for both visit0 and visit1 screenshots
                    visit0_screenshot = os.path.join(screenshot_base_dir, domain, f"visit0_{profile}.png")
                    visit1_screenshot = os.path.join(screenshot_base_dir, domain, f"visit1_{profile}.png")
                    
                    # Only consider it complete if data file and BOTH screenshots exist
                    if (os.path.exists(domain_file) and 
                        os.path.exists(visit0_screenshot) and 
                        os.path.exists(visit1_screenshot)):
                        existing_data[profile].add(domain)
                    
                    domain_pbar.update(1)
            
            pbar.update(1)
    
    if verbose:
        for profile, domains in existing_data.items():
            print(f"Profile {profile} has complete data (JSON + both screenshots) for {len(domains)} domains")
    
    return existing_data

async def crawl_sites_parallel(config, profiles_ids, sites, max_concurrent=None, subpages_nr=2, verbose=False):
    """
    Crawl sites in parallel with multiple browser profiles
    
    Args:
        config: Configuration dictionary
        profiles_ids: Dictionary mapping profile names to profile IDs
        sites: List of (rank, domain) tuples to crawl
        max_concurrent: Maximum number of concurrent browsers to run (None=all)
        subpages_nr: Number of subpages to crawl per site
        verbose: If True, print detailed progress information
    """
    profile_names = list(profiles_ids.keys())
    
    # If max_concurrent is not specified, use all available profiles
    if max_concurrent is None:
        max_concurrent = len(profile_names)
        if verbose:
            print(f"Using all {max_concurrent} profiles concurrently")
    
    # Pre-check which domain+extension combinations already have data
    existing_data = precheck_existing_data(profile_names, sites, verbose)
    
    # Calculate remaining crawls (excluding ones with existing data)
    remaining_crawls = 0
    for profile in profile_names:
        for rank, domain in sites:
            if domain not in existing_data[profile]:
                remaining_crawls += 1
    
    if verbose:
        print(f"Remaining crawls to perform: {remaining_crawls}")
    
    # Create semaphore to limit concurrent crawls
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create overall progress bar for all sites
    with tqdm(total=remaining_crawls, desc="Overall crawl progress", unit="site") as overall_pbar:
        
        async def profile_crawl_with_semaphore(profile_name, profile_id):
            """Wrapper to handle semaphore for each profile crawl"""
            async with semaphore:
                # Filter out domains that already have data for this profile
                sites_to_crawl = [(rank, domain) for rank, domain in sites 
                                  if domain not in existing_data[profile_name]]
                
                if not sites_to_crawl:
                    if verbose:
                        print(f"No sites to crawl for profile {profile_name} - all data exists")
                    return
                
                await crawl_with_profile(
                    config=config,
                    profile_name=profile_name,
                    profile_id=profile_id,
                    sites=sites_to_crawl,
                    subpages_nr=subpages_nr,
                    verbose=verbose,
                    overall_progress=overall_pbar
                )
        
        # Create tasks for all profiles
        tasks = []
        for profile_name, profile_id in profiles_ids.items():
            tasks.append(profile_crawl_with_semaphore(profile_name, profile_id))
        
        # Run all tasks
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Load configuration
    config = load_config('config.json')
    
    # Get Kameleo profile IDs
    profiles_ids = get_profiles_ids()
    
    # Get all sites
    sites = get_all_sites()
    if not sites:
        print("No sites available to crawl")
        exit(1)
    
    # Calculate total sites to crawl
    total_sites = len(profiles_ids) * len(sites)
    
    print(f"\nStarting parallel crawl of {len(sites)} sites with {len(profiles_ids)} profiles")
    print(f"Total site visits to perform: {total_sites}")
    
    # Run the parallel crawl
    asyncio.run(crawl_sites_parallel(
        config=config,
        profiles_ids=profiles_ids,
        sites=sites,
        max_concurrent=2, # 2 browsers limit :(
        subpages_nr=20,
        verbose=False
    ))
    
    print("\nCrawls completed!") 