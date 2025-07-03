import asyncio
import os
from utils.util import load_config, construct_paths, create_temp_profile_copy
from crawler.page_crawler import WebsiteCrawler


async def run_interaction_demo(profile1="no_extensions", profile2="adblock", domain="amazon.com", subpages_nr=3):
    """
    Run a side-by-side interaction demo with two profiles
    
    Args:
        profile1: First browser profile name
        profile2: Second browser profile name
        domain: Domain to visit
        subpages_nr: Number of subpages to visit
    """
    # Set window configuration for side-by-side display
    window_size = (850, 1200)
    window_position1 = (0, 0)
    window_position2 = (850, 0)
    
    # Load configuration
    config = load_config('config.json')
    
    # Get profile paths
    user_data_dir1, full_extension_path1 = construct_paths(config, profile1)
    user_data_dir2, full_extension_path2 = construct_paths(config, profile2)
    
    # Create temporary profile copies
    temp_profile_dir1 = create_temp_profile_copy(user_data_dir1, verbose=False)
    temp_profile_dir2 = create_temp_profile_copy(user_data_dir2, verbose=False)
        
    slow_mo = 200
    visits = 1
    verbose = False

    
    # Create WebsiteCrawler instances with demo mode enabled
    crawler1 = WebsiteCrawler(
        subpages_nr=subpages_nr,
        visits=visits,
        verbose=verbose,
        monitors=None,
        extension_name=profile1,
        headless=False,
        viewport={'width': window_size[0], 'height': window_size[1]},
        domain=domain,
        channel='chromium',
        window_position=window_position1,
        window_size=window_size,
        demo=True,
        slow_mo=slow_mo
    )
    
    crawler2 = WebsiteCrawler(
        subpages_nr=subpages_nr,
        visits=visits,
        verbose=verbose,
        monitors=None,
        extension_name=profile2,
        headless=False,
        viewport={'width': window_size[0], 'height': window_size[1]},
        domain=domain,
        channel='chromium',
        window_position=window_position2,
        window_size=window_size,
        demo=True,
        slow_mo=slow_mo
    )
    
    try:
        # Run both crawlers in parallel - each will create its own Playwright instance
        results = await asyncio.gather(
            crawler1.crawl_site(domain, user_data_dir=temp_profile_dir1, full_extension_path=full_extension_path1),
            crawler2.crawl_site(domain, user_data_dir=temp_profile_dir2, full_extension_path=full_extension_path2),
            return_exceptions=True
        )
        
        # Wait for observation
        await asyncio.sleep(15)
        
    except Exception as e:
        pass
        
    finally:
        # Cleanup temporary directories
        for temp_dir in [temp_profile_dir1, temp_profile_dir2]:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    pass


if __name__ == "__main__":
    profile1 = "consent_o_matic_opt_out"
    profile2 = "super_agent_opt_out"
    domain = "reddit.com"
    subpages_nr = 15
    
    asyncio.run(run_interaction_demo(
        profile1=profile1,
        profile2=profile2,
        domain=domain,
        subpages_nr=subpages_nr
    ))
    
    print("\nDemo completed!") 