import asyncio
import os
from crawl import crawl_domain
from utils.util import load_config, get_all_sites, construct_paths, create_temp_profile_copy
from tqdm import tqdm

async def crawl_sites_parallel(config, profiles, site_info, max_concurrent=3, max_pages=2, verbose=False):
    """
    Crawl one site with multiple browser profiles in parallel
    
    Args:
        config: Configuration dictionary
        profiles: List of browser profiles to use
        site_info: Tuple of (rank, domain) for the site to crawl
        max_concurrent: Maximum number of concurrent crawls
        max_pages: Maximum pages to crawl per site
        verbose: If True, print detailed progress information
    """
    # Create semaphore to limit concurrent crawls
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def crawl_with_semaphore(profile):
        """Wrapper to handle semaphore and error handling for each crawl"""
        async with semaphore:
            temp_profile_dir = None
            try:
                rank, domain = site_info
                if verbose:
                    print(f"\nStarting crawl of {domain} with profile: {profile}")
                
                # Get the original profile paths
                user_data_dir, full_extension_path = construct_paths(config, profile)
                
                # Create a temporary copy of the profile
                temp_profile_dir = create_temp_profile_copy(user_data_dir, verbose)
                
                if verbose:
                    print(f"Created temporary profile at: {temp_profile_dir}")
                
                # Skip extension path for no_extensions profile
                if profile == 'no_extensions':
                    full_extension_path = None
                
                await crawl_domain(
                    profile=profile,
                    site_info=site_info,
                    data_dir=temp_profile_dir,
                    max_pages=max_pages,
                    verbose=verbose
                )
                
                if verbose:
                    print(f"Completed crawl of {domain} with profile: {profile}")
                    
            except Exception as e:
                print(f"Error crawling {domain} with profile {profile}: {str(e)}")
            finally:
                # Cleanup temporary profile directory
                if temp_profile_dir and os.path.exists(temp_profile_dir):
                    if verbose:
                        print(f"Cleaning up temporary profile: {temp_profile_dir}")
                    import shutil
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
    
    # Create tasks for all profiles
    tasks = [crawl_with_semaphore(profile) for profile in profiles]
    
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
    verbose = True
    
    # Get available profiles
    profiles = config.get('profiles', {}).keys()
    
    # Get all sites and select one for testing
    sites = get_all_sites()
    if not sites:
        print("No sites available to crawl")
        exit(1)
    
    # Just use the first site
    site_info = sites[0]
    rank, domain = site_info
    
    print(f"\nStarting parallel crawl of {domain} (rank: {rank})")
    print(f"Using {len(profiles)} different profiles")
    
    # Run the parallel crawl
    asyncio.run(crawl_sites_parallel(
        config=config,
        profiles=profiles,
        site_info=site_info,
        max_concurrent=3,
        max_pages=2,
        verbose=verbose
    ))
    
    print("\nTest crawls completed!")