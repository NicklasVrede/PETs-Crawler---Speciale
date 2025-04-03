import asyncio
import os
import random
from crawl import crawl_domain
from utils.util import load_config, get_all_sites, construct_paths, create_temp_profile_copy
from tqdm import tqdm
from collections import defaultdict

async def crawl_with_profile(config, profile, sites, subpages_nr=2, verbose=False, overall_progress=None):
    """
    Crawl multiple sites with a single browser profile
    
    Args:
        config: Configuration dictionary
        profile: Browser profile to use
        sites: List of (rank, domain) tuples to crawl
        max_pages: Maximum pages to crawl per site
        verbose: If True, print detailed progress information
        overall_progress: Overall progress bar to update
    """
    temp_profile_dir = None
    try:
        # Get the original profile paths
        user_data_dir, full_extension_path = construct_paths(config, profile)
        
        # Create a temporary copy of the profile - once per browser profile
        temp_profile_dir = create_temp_profile_copy(user_data_dir, verbose)
        
        if verbose:
            print(f"Created temporary profile for {profile} at: {temp_profile_dir}")
        
        # Skip extension path for no_extensions profile
        if profile == 'no_extensions':
            full_extension_path = None
            
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
                    print(f"Crawling {domain} with profile {profile}")
                
                await crawl_domain(
                    profile=profile,
                    site_info=site_info,
                    data_dir=temp_profile_dir,
                    subpages_nr=subpages_nr,
                    verbose=verbose,
                    skip_existence_check=True  # Skip the check since we've done it already
                )
                
                if verbose:
                    print(f"Completed crawl of {domain} with profile {profile}")
                
                # Update the overall progress bar if provided
                if overall_progress:
                    overall_progress.update(1)
                    
            except Exception as e:
                print(f"Error crawling {domain} with profile {profile}: {str(e)}")
                # Continue with the next site even if this one fails
                
                # Still update the overall progress bar for failed crawls
                if overall_progress:
                    overall_progress.update(1)
    finally:
        # Cleanup temporary profile directory
        if temp_profile_dir and os.path.exists(temp_profile_dir):
            if verbose:
                print(f"Cleaning up temporary profile: {temp_profile_dir}")
            import shutil
            shutil.rmtree(temp_profile_dir, ignore_errors=True)

def precheck_existing_data(profiles, sites, verbose=False):
    """
    Pre-check which domain+extension combinations already have data
    
    Args:
        profiles: List of profiles/extensions to check
        sites: List of (rank, domain) tuples to check
        verbose: Whether to print verbose output
        
    Returns:
        Dictionary mapping profile -> set of domains with existing data
    """
    if verbose:
        print("Pre-checking existing data files...")
    
    # Create a dictionary to store results
    existing_data = defaultdict(set)
    base_dir = "data/crawler_data"
    
    # Check each profile directory
    with tqdm(total=len(profiles), desc="Checking profiles", unit="profile") as pbar:
        for profile in profiles:
            profile_dir = os.path.join(base_dir, profile)
            if not os.path.exists(profile_dir):
                if verbose:
                    print(f"  Creating directory for {profile}")
                os.makedirs(profile_dir, exist_ok=True)
                pbar.update(1)
                continue
                
            # Get all existing files for this profile
            try:
                existing_files = [f for f in os.listdir(profile_dir) if f.endswith('.json')]
                
                # Use nested progress bar for files within each profile
                with tqdm(total=len(existing_files), desc=f"Checking {profile}", 
                          unit="file", leave=False) as file_pbar:
                    for filename in existing_files:
                        # Extract domain name from filename
                        domain = filename[:-5]  # Remove .json extension
                        
                        # Check if file has more than 10 lines
                        file_path = os.path.join(profile_dir, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            line_count = sum(1 for _ in f)
                        
                        if line_count > 10:
                            existing_data[profile].add(domain)
                        elif verbose:
                            print(f"  Skipping {filename} for {profile} - only has {line_count} lines")
                        
                        file_pbar.update(1)
                        
            except Exception as e:
                print(f"Error checking {profile_dir}: {e}")
            
            pbar.update(1)
    
    # Statistics for verbose output
    if verbose:
        total_existing = sum(len(domains) for domains in existing_data.values())
        total_possible = len(profiles) * len(sites)
        print(f"Found {total_existing} existing data files out of {total_possible} possible combinations")
        print(f"Remaining to crawl: {total_possible - total_existing}")
    
    return existing_data

async def crawl_sites_parallel(config, profiles, sites, max_concurrent=None, subpages_nr=2, verbose=False):
    """
    Crawl multiple sites with multiple browser profiles in parallel
    
    Args:
        config: Configuration dictionary
        profiles: List of browser profiles to use
        sites: List of (rank, domain) tuples for the sites to crawl
        max_concurrent: Maximum number of concurrent browser instances. If None, use all profiles.
        max_pages: Maximum pages to crawl per site
        verbose: If True, print detailed progress information
    """
    # If max_concurrent is not specified, use all available profiles
    if max_concurrent is None:
        max_concurrent = len(profiles)
        if verbose:
            print(f"Using all {max_concurrent} profiles concurrently")
    
    # Pre-check which domain+extension combinations already have data
    existing_data = precheck_existing_data(profiles, sites, verbose)
    
    # Calculate remaining crawls (excluding ones with existing data)
    remaining_crawls = 0
    for profile in profiles:
        for rank, domain in sites:
            if domain not in existing_data[profile]:
                remaining_crawls += 1
    
    if verbose:
        print(f"Remaining crawls to perform: {remaining_crawls}")
    
    # Create semaphore to limit concurrent crawls
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create overall progress bar for all sites
    with tqdm(total=remaining_crawls, desc="Overall crawl progress", unit="site") as overall_pbar:
        
        async def profile_crawl_with_semaphore(profile):
            """Wrapper to handle semaphore for each profile crawl"""
            async with semaphore:
                # Filter out domains that already have data for this profile
                sites_to_crawl = [(rank, domain) for rank, domain in sites 
                                  if domain not in existing_data[profile]]
                
                if not sites_to_crawl:
                    if verbose:
                        print(f"No sites to crawl for profile {profile} - all data exists")
                    return
                
                await crawl_with_profile(
                    config=config,
                    profile=profile,
                    sites=sites_to_crawl,
                    subpages_nr=subpages_nr,
                    verbose=verbose,
                    overall_progress=overall_pbar
                )
        
        # Create tasks for all profiles
        tasks = [profile_crawl_with_semaphore(profile) for profile in profiles]
        
        # Run all tasks
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Load configuration
    config = load_config('config.json')
    verbose = False
    
    # Get available profiles
    profiles = config.get('profiles', {}).keys()
    
    # Get all sites
    sites = get_all_sites()
    if not sites:
        print("No sites available to crawl")
        exit(1)
    
    # Calculate total sites to crawl
    total_sites = len(profiles) * len(sites)
    
    print(f"\nStarting parallel crawl of {len(sites)} sites with {len(profiles)} profiles")
    print(f"Total site visits to perform: {total_sites}")
    
    # Run the parallel crawl
    asyncio.run(crawl_sites_parallel(
        config=config,
        profiles=profiles,
        sites=sites,
        max_concurrent=16,
        subpages_nr=20,
        verbose=verbose
    ))
    
    print("\nCrawls completed!")