import asyncio
import requests
import json
from playwright.async_api import async_playwright

async def test_kameleo():
    """Simple test function to verify Kameleo connection and functionality"""
    print("\n=== Kameleo Connection Test Using Official Format ===")
    
    # Get profiles from the working endpoint
    profiles_url = "http://localhost:5050/profiles"
    kameleo_port = 5050
    
    try:
        response = requests.get(profiles_url)
        profiles = response.json()
        print(f"Found {len(profiles)} profiles:")
        
        for i, profile in enumerate(profiles):
            profile_id = profile.get('id')
            profile_state = profile.get('state')
            print(f"{i+1}. ID: {profile_id}, State: {profile_state}")
            
            # Check if profile is running
            if profile_state != "RUNNING":
                print(f"Profile is not running. Attempting to start profile {profile_id}...")
                start_url = f"http://localhost:5050/profiles/{profile_id}/start"
                try:
                    start_response = requests.post(start_url)
                    print(f"Start response: {start_response.status_code}")
                    # Give it a moment to startA
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"Failed to start profile: {e}")
                    continue
            
            # Using the official format
            browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{profile_id}'
            print(f"Connecting to: {browser_ws_endpoint}")
            
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)
                    print(f"✅ SUCCESS! Connected to browser")
                    
                    # Get the default context
                    context = browser.contexts[0]
                    
                    # Create a new page as shown in the official example
                    print("Creating new page...")
                    page = await context.new_page()
                    
                    # Navigate to example.com
                    print("Navigating to example.com...")
                    await page.goto("https://example.com")
                    
                    # Get the page title
                    title = await page.title()
                    print(f"Page title: {title}")
                    
                    # Take a screenshot
                    screenshot_path = f"kameleo_profile_{i+1}_screenshot.png"
                    await page.screenshot(path=screenshot_path)
                    print(f"Screenshot saved to {screenshot_path}")
                    
                    # Keep the page open for a while so you can see it
                    print("Keeping browser open for 60 seconds. Press Ctrl+C to exit early.")
                    await page.wait_for_timeout(60000)
                    
                    # Disconnect without closing the Kameleo profile
                    await browser.close()
                    print("Successfully tested connection")
                    
                except Exception as e:
                    print(f"Error connecting to browser: {e}")
    
    except Exception as e:
        print(f"Error connecting to Kameleo: {e}")

if __name__ == "__main__":
    asyncio.run(test_kameleo()) 