#!/usr/bin/env python3
"""
Run multiple crawls in parallel
"""
import asyncio
import os
import time
import shutil
import random
from crawl_seq import crawl_domain
from utils.util import get_all_sites
from tqdm import tqdm

async def crawl_all_domains(profile, site_list, max_parallel=3, max_pages=2, verbose=False):
    """
    Crawl multiple domains in parallel
    
    Args:
        profile: Browser profile to use
        site_list: List of (rank, domain) tuples
        max_parallel: Maximum number of parallel crawls
        max_pages: Maximum pages per domain
        verbose: Enable verbose output
    """
    # Create semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(max_parallel)
    total_domains = len(site_list)
    
    # Create overall progress bar for domains
    domain_progress = tqdm(total=total_domains, desc="Crawling domains", unit="domain", position=0)
    
    # Track timing
    start_time = time.time()
    
    # Temp directory base path
    temp_base_dir = os.path.join("data", "temp_profiles")
    os.makedirs(temp_base_dir, exist_ok=True)
    
    async def crawl_with_semaphore(site_info):
        """Wrapper to manage semaphore and update progress"""
        async with semaphore:
            # Get site info
            rank, domain = site_info
            
            # Add a small random delay between browser launches to reduce resource contention
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Create a unique data directory for this crawl - without timestamp
            domain_safe = domain.lower().replace('.', '_')
            temp_dir = os.path.join(temp_base_dir, f"profile_{domain_safe}")
            
            # create the directory
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # Actually do the crawl
                await crawl_domain(
                    profile, 
                    site_info, 
                    data_dir=temp_dir,
                    max_pages=max_pages, 
                    verbose=False
                )
                
                # Update elapsed time info in progress bar
                elapsed = time.time() - start_time
                avg_time = elapsed / (domain_progress.n + 1)  # Adding 1 because we're about to increment
                eta = avg_time * (total_domains - domain_progress.n - 1)
                domain_progress.set_postfix(
                    avg=f"{avg_time:.1f}s/domain", 
                    eta=f"{eta/60:.1f}min"
                )
                
            except Exception as e:
                tqdm.write(f"Error crawling {domain}: {str(e)}")
            finally:
                # Update progress counter
                domain_progress.update(1)
                
                # Add a small delay after finishing to let system resources recover
                await asyncio.sleep(0.5)
    
    try:
        # Create tasks for all domains
        tasks = [crawl_with_semaphore(site_info) for site_info in site_list]
        
        # Run all tasks
        await asyncio.gather(*tasks)
    finally:
        # Close the progress bar
        domain_progress.close()
    
    # Final report
    total_time = time.time() - start_time
    tqdm.write(f"\nCrawl completed: {total_domains} domains in {total_time/60:.1f} minutes")

def main():
    """Main function with hard-coded parameters"""
    # Set your parameters directly here
    profile = "i_dont_care_about_cookies"
    parallel = 3  # Reduced from 5 to avoid resource issues
    max_pages = 20
    start_index = 0
    count = 100  # Set to None to crawl all sites
    csv_file = "data/study-sites.csv"
    verbose = False
    
    # Get list of sites
    tqdm.write(f"Loading sites from {csv_file}...")
    all_sites = get_all_sites(csv_file)
    
    # Determine which sites to crawl
    end_index = start_index + count if count else len(all_sites)
    sites_to_crawl = all_sites[start_index:end_index]
    
    tqdm.write(f"Will crawl {len(sites_to_crawl)} sites starting from index {start_index}")
    tqdm.write(f"Using profile: {profile}")
    tqdm.write(f"Max parallel crawls: {parallel}")
    tqdm.write(f"Max pages per domain: {max_pages}")
    
    # Run the crawl
    asyncio.run(crawl_all_domains(
        profile, 
        sites_to_crawl, 
        max_parallel=parallel, 
        max_pages=max_pages,
        verbose=verbose
    ))

if __name__ == "__main__":
    main() 