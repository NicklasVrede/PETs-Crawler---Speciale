import random
import asyncio
from playwright.async_api import Page
from tqdm import tqdm

class UserSimulator:
    def __init__(self, seed=42):
        # Set seed for reproducibility
        self.random = random.Random(seed)
        self.scroll_probability = 0.7
        self.click_probability = 0.3
        self.max_scroll_attempts = 2
        self.max_click_attempts = 1

    async def simulate_interaction(self, page: Page, url=None):
        """Simulate realistic user interaction on the page"""
        try:
            # If URL is provided, use it to create a deterministic seed for this page
            if url:
                # Create a page-specific random generator
                page_seed = hash(url) % 10000
                page_random = random.Random(page_seed)
            else:
                # Fallback to the instance random generator
                page_random = self.random
                
            # Ensure page is ready
            await page.wait_for_load_state('domcontentloaded')
            
            # Fixed initial delay
            await asyncio.sleep(0.5)

            # Always perform the same scrolling for the same URL
            await self._perform_scrolling(page, url)

            # Deterministic decision to click based on URL
            should_click = page_random.random() < self.click_probability
            if should_click:
                await self._attempt_clicking(page, page_random)

        except Exception as e:
            tqdm.write(f"Error during user simulation: {e}")

    async def _move_mouse(self, page: Page, x_percentage=0.5, y_percentage=0.5):
        """Move mouse to a deterministic position within the viewport"""
        try:
            # Get viewport dimensions
            page_dimensions = await page.evaluate('''() => {
                return {
                    width: document.documentElement.clientWidth,
                    height: document.documentElement.clientHeight
                }
            }''')
            
            # Calculate exact position based on percentages
            target_x = int(page_dimensions['width'] * x_percentage)
            target_y = int(page_dimensions['height'] * y_percentage)
            
            # Move mouse with fixed steps
            await page.mouse.move(
                target_x,
                target_y,
                steps=10  # Fixed number of steps
            )
            
            # Fixed pause after movement
            await asyncio.sleep(0.2)
            
        except Exception as e:
            tqdm.write(f"Error during mouse movement: {e}")

    async def _perform_scrolling(self, page: Page, url=None):
        """Perform deterministic scrolling actions based on URL"""
        try:
            # Calculate deterministic positions based on URL
            if url:
                # Generate a hash from the URL for deterministic behavior
                url_hash = hash(url) % 1000
                # Use the hash to determine scroll pattern (between 40-60%)
                scroll_percentage = 0.4 + ((url_hash % 20) / 100)
                # Determine mouse position before scrolling
                mouse_x = 0.3 + ((url_hash % 40) / 100)  # 30-70%
                mouse_y = 0.2 + ((url_hash % 60) / 100)  # 20-80%
            else:
                # Default values if no URL
                scroll_percentage = 0.5  # 50%
                mouse_x = 0.5  # center
                mouse_y = 0.5  # center
            
            # Move mouse to deterministic position
            await self._move_mouse(page, mouse_x, mouse_y)
            
            # Get page dimensions
            metrics = await page.evaluate('''() => {
                return {
                    height: document.documentElement.scrollHeight,
                    viewportHeight: window.innerHeight,
                    availableScroll: document.documentElement.scrollHeight - window.innerHeight
                }
            }''')
            
            if metrics['availableScroll'] <= 0:
                return

            # Calculate target scroll position based on predetermined percentage
            available_scroll = metrics['availableScroll']
            target_scroll = int(available_scroll * scroll_percentage)
            
            # Fixed scroll increment (you could vary this based on URL too if needed)
            increment = 300
            
            # Pre-calculate the exact number of steps needed
            steps = (target_scroll + increment - 1) // increment  # ceiling division
            
            # Perform deterministic scrolling with exactly the right number of steps
            for step in range(steps):
                next_position = min((step + 1) * increment, target_scroll)
                
                # Perform the scroll
                await page.evaluate(f'''() => {{
                    window.scrollTo({{
                        top: {next_position},
                        behavior: "smooth"
                    }});
                }}''')
                
                # Fixed wait between scrolls
                await asyncio.sleep(0.3)

        except Exception as e:
            tqdm.write(f"Error during scrolling: {e}")

    async def _attempt_clicking(self, page: Page, page_random):
        """Attempt to click on some safe elements using deterministic selection"""
        try:
            safe_selectors = [
                'button:not([type="submit"])',
                'a[href^="#"]',
                '.tab',
                '[role="tab"]',
                '.accordion',
                '[aria-expanded]'
            ]

            # Use a fixed order based on the page seed
            selector_indices = list(range(len(safe_selectors)))
            page_random.shuffle(selector_indices)
            
            for idx in selector_indices:
                selector = safe_selectors[idx]
                try:
                    is_visible = await page.is_visible(selector, timeout=1000)
                    if is_visible:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            # Select element deterministically
                            element_index = page_random.randint(0, len(elements) - 1)
                            element = elements[element_index]
                            await element.click(timeout=1000)
                            await asyncio.sleep(0.4)
                            break
                except Exception:
                    continue

        except Exception as e:
            tqdm.write(f"Error during clicking: {e}") 