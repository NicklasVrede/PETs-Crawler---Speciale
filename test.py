import asyncio
from playwright.async_api import async_playwright
import os

async def open_browser_with_extension():
    user_data_dir = r"C:\Users\Nickl\AppData\Local\ms-playwright\User_profiles\consent_o_matic"
    extension_path = os.path.join(user_data_dir, 'Default', 'Extensions', 'mdjildafknihdffpkfmmpnpoiajfjnjd', '1.1.3_0')
    
    # Print the extension path
    print(f"Extension path: {extension_path}")

    async with async_playwright() as p:
        # Launch a persistent context with the specified user data directory and extension
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,  # Set to False to see the browser window
            args=[
                f'--disable-extensions-except={extension_path}',
                f'--load-extension={extension_path}'
            ]
        )
    
        # Wait for a few seconds to observe the browser
        await asyncio.sleep(120)
        
        # Close the browser
        await browser.close()

# Run the test
asyncio.run(open_browser_with_extension())
