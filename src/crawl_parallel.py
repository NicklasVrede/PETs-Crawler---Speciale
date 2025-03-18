import asyncio
import os
import random
from crawl import crawl_domain
from utils.util import load_config, get_all_sites, construct_paths, create_temp_profile_copy
from tqdm import tqdm

async def crawl_with_profile(config, profile, sites, max_pages=2, verbose=False):
    """
    Crawl multiple sites with a single browser profile
    
    Args:
        config: Configuration dictionary
        profile: Browser profile to use
        sites: List of (rank, domain) tuples to crawl
        max_pages: Maximum pages to crawl per site
        verbose: If True, print detailed progress information
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
                    max_pages=max_pages,
                    verbose=verbose
                )
                
                if verbose:
                    print(f"Completed crawl of {domain} with profile {profile}")
            except Exception as e:
                print(f"Error crawling {domain} with profile {profile}: {str(e)}")
                # Continue with the next site even if this one fails
    finally:
        # Cleanup temporary profile directory
        if temp_profile_dir and os.path.exists(temp_profile_dir):
            if verbose:
                print(f"Cleaning up temporary profile: {temp_profile_dir}")
            import shutil
            shutil.rmtree(temp_profile_dir, ignore_errors=True)

async def crawl_sites_parallel(config, profiles, sites, max_concurrent=3, max_pages=2, verbose=False):
    """
    Crawl multiple sites with multiple browser profiles in parallel
    
    Args:
        config: Configuration dictionary
        profiles: List of browser profiles to use
        sites: List of (rank, domain) tuples for the sites to crawl
        max_concurrent: Maximum number of concurrent browser instances
        max_pages: Maximum pages to crawl per site
        verbose: If True, print detailed progress information
    """
    # Create semaphore to limit concurrent crawls
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def profile_crawl_with_semaphore(profile):
        """Wrapper to handle semaphore for each profile crawl"""
        async with semaphore:
            await crawl_with_profile(
                config=config,
                profile=profile,
                sites=sites,
                max_pages=max_pages,
                verbose=verbose
            )
    
    # Create tasks for all profiles
    tasks = [profile_crawl_with_semaphore(profile) for profile in profiles]
    
    # Use tqdm to show progress
    with tqdm(total=len(profiles), desc="Crawling with different profiles", unit="profile") as pbar:
        # Wrap each task to update the progress bar
        async def wrap_task(task):
            await task
            pbar.update(1)
        
        # Run all tasks
        await asyncio.gather(*(wrap_task(task) for task in tasks))

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
    
    print(f"\nStarting parallel crawl of {len(sites)} sites")
    print(f"Using {len(profiles)} different browser profiles")
    
    # Run the parallel crawl
    asyncio.run(crawl_sites_parallel(
        config=config,
        profiles=profiles,
        sites=sites,
        max_concurrent=3,
        max_pages=2,
        verbose=verbose
    ))
    
    print("\nCrawls completed!")