import asyncio
import os
import random
from crawl import crawl_domain
from utils.util import load_config, get_all_sites, construct_paths, create_temp_profile_copy
from tqdm import tqdm

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
                    verbose=verbose
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
    
    # Create semaphore to limit concurrent crawls
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Calculate total number of crawls (profiles × sites)
    total_crawls = len(profiles) * len(sites)
    
    # Create overall progress bar for all sites
    with tqdm(total=total_crawls, desc="Overall crawl progress", unit="site") as overall_pbar:
        
        async def profile_crawl_with_semaphore(profile):
            """Wrapper to handle semaphore for each profile crawl"""
            async with semaphore:
                await crawl_with_profile(
                    config=config,
                    profile=profile,
                    sites=sites,
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
        max_concurrent=8,
        subpages_nr=5,
        verbose=verbose
    ))
    
    print("\nCrawls completed!")