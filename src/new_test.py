import asyncio
import requests
import json
from playwright.async_api import async_playwright
import time
from kameleo.local_api_client import KameleoLocalApiClient
from pprint import pprint
from kameleo.local_api_client.builder_for_create_profile import BuilderForCreateProfile
from kameleo.local_api_client.models import WebglMetaSpoofingOptions

kameleo_port = 5050
client = KameleoLocalApiClient()


# Get profiles using requests
profiles_url = f"http://localhost:{kameleo_port}/profiles"
response = requests.get(profiles_url)
all_profiles = response.json()

# Get the first profile
first_profile = all_profiles[0]
first_profile_id = first_profile['id']

print(f"Found {len(all_profiles)} total profiles")
print(f"First profile ID: {first_profile_id}")
print(f"First profile name: {first_profile['name']}")

async def connect_to_profile(browser_ws_endpoint):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)
    context = browser.contexts[0]
    page = context.pages[0]
    return page, context, browser, playwright

async def main():
    # Connect to the profile
    browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{first_profile_id}'
    page, context, browser, playwright = await connect_to_profile(browser_ws_endpoint)
    
    try:
        await asyncio.sleep(3)

        await page.goto('https://www.google.com')
        await page.wait_for_timeout(5000)
        
        print(f'closing page')
    finally:
        # Properly close all resources
        for page in context.pages:
            await page.close()
        await playwright.stop()

# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())


