import asyncio
import logging
from playwright.async_api import async_playwright
from src.utils.user_simulator import UserSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AmazonCrawlerTest:
    def __init__(self):
        # Using UserSimulator with verbose mode enabled
        self.user_simulator = UserSimulator(seed=42, verbose=True)
        
    async def run_test(self, num_iterations=2):
        """Run multiple iterations to verify deterministic behavior"""
        test_url = "https://www.amazon.co.uk/"
        
        async with async_playwright() as p:
            for i in range(num_iterations):
                logger.info(f"=== ITERATION {i+1} with URL: {test_url} ===")
                
                # Create a completely fresh browser for each test to avoid any state persistence
                browser = await p.chromium.launch(headless=False)
                
                # Create a new incognito context with no persistent storage
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    has_touch=False,
                    locale="en-GB",
                    timezone_id="Europe/London",
                    # Explicitly disable all storage persistence
                    storage_state=None  
                )
                
                page = await context.new_page()
                
                # Navigate to Amazon
                logger.info(f"Navigating to {test_url}")
                await page.goto(test_url, wait_until="domcontentloaded")
                
                # Accept cookies if the dialog appears
                try:
                    accept_button = await page.wait_for_selector(
                        "#sp-cc-accept", 
                        timeout=5000
                    )
                    if accept_button:
                        await accept_button.click()
                        logger.info("Accepted cookies")
                except Exception:
                    logger.info("No cookie dialog found or already accepted")
                
                # Run the user simulator
                logger.info("Running user simulator...")
                await self.user_simulator.simulate_interaction(page, url=test_url)
                
                # Wait to observe the results
                logger.info("Finished simulation, waiting 3 seconds before closing...")
                await asyncio.sleep(3)
                
                # Close everything for complete cleanup
                await context.close()
                await browser.close()

    async def run_multiple_urls_test(self):
        """Test with multiple URLs to demonstrate URL-based determinism"""
        # Different URLs that should produce different behaviors
        test_urls = [
            "https://www.amazon.co.uk/"
        ]
        
        async with async_playwright() as p:
            for url in test_urls:
                logger.info(f"=== TESTING URL: {url} ===")
                
                # Create a fresh browser for each URL test
                browser = await p.chromium.launch(headless=False)
                
                # Create a new incognito context with no persistent storage
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    locale="en-GB",
                    timezone_id="Europe/London",
                    storage_state=None
                )
                
                page = await context.new_page()
                
                # Navigate to the URL
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded")
                
                # Accept cookies if needed
                try:
                    accept_button = await page.wait_for_selector(
                        "#sp-cc-accept", 
                        timeout=5000
                    )
                    if accept_button:
                        await accept_button.click()
                        logger.info("Accepted cookies")
                except Exception:
                    logger.info("No cookie dialog found or already accepted")
                
                # Run the user simulator
                logger.info("Running user simulator...")
                await self.user_simulator.simulate_interaction(page, url=url)
                
                # Wait to observe the results
                logger.info("Finished simulation, waiting 3 seconds before closing...")
                await asyncio.sleep(3)
                
                # Close everything for complete cleanup
                await context.close()
                await browser.close()


async def main():
    test = AmazonCrawlerTest()
    
    # First run the standard test with multiple iterations on same URL
    logger.info("RUNNING STANDARD TEST WITH MULTIPLE ITERATIONS (SAME URL)")
    await test.run_test(num_iterations=2)
    
    # Then test with different URLs to verify URL-based determinism
    logger.info("\nRUNNING TEST WITH MULTIPLE DIFFERENT URLS")
    await test.run_multiple_urls_test()

if __name__ == "__main__":
    asyncio.run(main()) 