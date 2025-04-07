import asyncio
import requests
import json
from playwright.async_api import async_playwright

async def test_multiple_kameleo_profiles():
    """Test function to connect to multiple Kameleo profiles simultaneously"""
    print("\n=== Testing Multiple Kameleo Profiles ===")
    
    # Define profile names from your screenshots
    profile_names = [
        "disconnect", 
    ]
    kameleo_port = 5050
    
    # Get all profiles
    profiles_url = f"http://localhost:{kameleo_port}/profiles"
    
    try:
        response = requests.get(profiles_url)
        all_profiles = response.json()
        print(f"Found {len(all_profiles)} total profiles")
        
        # Find the specific profiles by name
        target_profiles = []
        for profile in all_profiles:
            profile_id = profile.get('id')
            name = profile.get('name', '')
            if name in profile_names:
                target_profiles.append(profile)
                print(f"Found target profile: {name} (ID: {profile_id})")
        
        if not target_profiles:
            print("Could not find the specified profiles!")
            return
            
        # Start all profiles and connect to them
        browsers = []
        
        async with async_playwright() as p:
            for profile in target_profiles:
                profile_id = profile.get('id')
                profile_name = profile.get('name', '')
                profile_state = profile.get('state')
                
                print(f"\nProcessing profile: {profile_name} (ID: {profile_id})")
                
                # Start the profile if not already running
                if profile_state != "RUNNING":
                    print(f"Starting profile {profile_name}...")
                    start_url = f"http://localhost:{kameleo_port}/profiles/{profile_id}/start"
                    try:
                        start_response = requests.post(start_url)
                        print(f"Start response: {start_response.status_code}")
                        # Give it a moment to start
                        await asyncio.sleep(5)
                    except Exception as e:
                        print(f"Failed to start profile: {e}")
                        continue
                
                # Connect to the profile
                try:
                    browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{profile_id}'
                    print(f"Connecting to: {browser_ws_endpoint}")
                    
                    browser = await p.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)
                    print(f"✅ Connected to {profile_name}")
                    browsers.append((browser, profile_name))
                    
                    
                    # Get the default context
                    context = browser.contexts[0]
                    
                    # Create a new page
                    print(f"Creating new page for {profile_name}...")
                    page = await context.new_page()
                    
                    # Navigate to a different site for each profile
                    test_sites = [
                        "https://example.com",
                        "https://google.com",
                        "https://bing.com",
                        "https://duckduckgo.com",
                        "https://apple.com",
                        "https://microsoft.com",
                        "https://wikipedia.org",
                        "https://github.com"
                    ]
                    
                    # Get the index of the profile in our list and use corresponding site
                    profile_index = profile_names.index(profile_name)
                    site_index = min(profile_index, len(test_sites) - 1)
                    url = test_sites[site_index]
                        
                    print(f"Navigating to {url} with {profile_name}...")
                    await page.goto(url)
                    
                    # Get page title
                    title = await page.title()
                    print(f"Page title for {profile_name}: {title}")
                    
                    # Take a screenshot
                    screenshot_path = f"{profile_name}_screenshot.png"
                    await page.screenshot(path=screenshot_path)
                    print(f"Screenshot saved to {screenshot_path}")
                    
                except Exception as e:
                    print(f"Error connecting to {profile_name}: {e}")
            
            # Keep browsers open for a while
            print("\nKeeping browsers open for 60 seconds. Press Ctrl+C to exit early.")
            await asyncio.sleep(60)
            
            # Close all browser connections (but don't stop the profiles)
            for browser, profile_name in browsers:
                print(f"Disconnecting from {profile_name}...")
                await browser.close()
            
            print("Test completed successfully")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_multiple_kameleo_profiles()) 