import asyncio
import os
import random
from crawl_kameleo import crawl_domain, get_profiles_ids
from utils.util import load_config, get_all_sites, construct_paths
from tqdm import tqdm
from collections import defaultdict
import requests
from pprint import pprint
import time

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
                
                retry_attempts = 3
                for attempt in range(retry_attempts):
                    try:
                        await crawl_domain(
                            profile_name=profile_name,
                            profile_id=profile_id,
                            site_info=site_info,
                            subpages_nr=subpages_nr,
                            verbose=verbose,
                            skip_existence_check=True  # Skip the check since we've done it already
                        )
                        break  # Success, exit retry loop
                    except Exception as e:
                        if "Parallel automated browsers limit exceeded" in str(e):
                            if attempt < retry_attempts - 1:  # Don't sleep on the last attempt
                                wait_time = (attempt + 1) * 5  # Progressive backoff: 5s, 10s, 15s
                                if verbose:
                                    print(f"Hit concurrent limit, waiting {wait_time}s before retry...")
                                await asyncio.sleep(wait_time)
                            else:
                                raise  # Re-raise on final attempt
                        else:
                            raise  # Re-raise other exceptions
                
                if verbose:
                    print(f"Completed crawl of {domain} with profile {profile_name}")
                
                # Update the overall progress bar if provided
                if overall_progress:
                    overall_progress.update(1)
                    
            except Exception as e:
                print(f"Error crawling {domain} with profile {profile_name}: {str(e)}")
                # Continue with the next site even if this one fails
                
                # Still update the overall progress bar for failed crawls
                if overall_progress:
                    overall_progress.update(1)
    except Exception as e:
        print(f"Error in crawl_with_profile for {profile_name}: {str(e)}")

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

async def crawl_sites_parallel(config, profiles_ids, sites, max_concurrent=None, subpages_nr=2, verbose=False):
    """
    Crawl multiple sites with multiple browser profiles in parallel using Kameleo
    
    Args:
        config: Configuration dictionary
        profiles_ids: Dictionary mapping profile names to Kameleo profile IDs
        sites: List of (rank, domain) tuples for the sites to crawl
        max_concurrent: Maximum number of concurrent browser instances. If None, use all profiles.
        subpages_nr: Number of subpages to crawl per site
        verbose: If True, print detailed progress information
    """
    # Get profile names
    profile_names = list(profiles_ids.keys())
    
    # If max_concurrent is not specified, use 1 by default due to Kameleo limitations
    if max_concurrent is None:
        max_concurrent = 1
    
    if verbose:
        print(f"Using {max_concurrent} concurrent browser(s) due to Kameleo limitations")
    
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
    verbose = True
    
    # Get Kameleo profile IDs
    profiles_ids = get_profiles_ids()
    
    # Print available profiles
    print("Available Kameleo profiles:")
    pprint(profiles_ids)
    
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
        max_concurrent=1,  # Set to 1 to avoid Kameleo's parallel limit
        subpages_nr=20,
        verbose=verbose
    ))
    
    print("\nCrawls completed!") 