import asyncio
import requests
from playwright.async_api import async_playwright

async def test_kameleo_connection():
    """Simplest possible test script to diagnose connection issues"""
    print("\n=== Testing Kameleo Connection ===")
    
    # Get profile ID
    kameleo_port = 5050
    response = requests.get(f"http://localhost:{kameleo_port}/profiles")
    profiles = response.json()
    
    if not profiles:
        print("No profiles available!")
        return
    
    profile_id = profiles[0].get('id')
    profile_name = profiles[0].get('name')
    print(f"Using profile: {profile_name} (ID: {profile_id})")
    
    # Start the profile
    print(f"Starting profile...")
    start_url = f"http://localhost:{kameleo_port}/profiles/{profile_id}/start"
    start_response = requests.post(start_url)
    print(f"Start response: {start_response.status_code}")
    await asyncio.sleep(2)
    
    # Connect to the profile via WebSocket
    browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{profile_id}'
    print(f"Connecting to: {browser_ws_endpoint}")
    
    async with async_playwright() as p:
        try:
            # This is the key part - connect to the WebSocket endpoint
            browser = await p.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)
            print("Successfully connected to browser!")
            
            # Test creating a page and navigating
            context = browser.contexts[0]
            page = await context.new_page()
            print("Created new page")
            
            await page.goto("https://example.com")
            title = await page.title()
            print(f"Page loaded. Title: {title}")
            
            await browser.close()
            print("Test completed successfully")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_kameleo_connection()) 