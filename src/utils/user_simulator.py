import random
import asyncio
from playwright.async_api import Page

class UserSimulator:
    def __init__(self, verbose=False):
        self.scroll_probability = 0.7
        self.click_probability = 0.3
        self.max_scroll_attempts = 2
        self.max_click_attempts = 1
        self.verbose = verbose

    async def simulate_interaction(self, page: Page):
        """Simulate realistic user interaction on the page"""
        try:
            # Ensure page is ready
            await page.wait_for_load_state('domcontentloaded')
            
            # Short initial delay
            await asyncio.sleep(random.uniform(0.3, 0.7))

            # Always try to scroll at least once
            await self._perform_scrolling(page)

            # Maybe click something (with shorter timeout)
            if random.random() < self.click_probability:
                await self._attempt_clicking(page)

        except Exception as e:
            if self.verbose:
                print(f"Error during user simulation: {e}")

    async def _move_mouse(self, page: Page):
        """Move mouse to a position within the viewport"""
        try:
            # Get viewport dimensions
            page_dimensions = await page.evaluate('''() => {
                return {
                    width: document.documentElement.clientWidth,
                    height: document.documentElement.clientHeight
                }
            }''')
            
            # Generate coordinates within the viewport (with margins)
            target_x = random.randint(50, page_dimensions['width'] - 50)
            target_y = random.randint(50, page_dimensions['height'] - 50)
            
            # Move mouse with steps
            await page.mouse.move(
                target_x,
                target_y,
                steps=random.randint(10, 20)
            )
            
            # Short pause after movement
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
        except Exception as e:
            if self.verbose:
                print(f"Error during mouse movement: {e}")

    async def _perform_scrolling(self, page: Page):
        """Perform some scrolling actions"""
        try:
            # Move mouse before scrolling
            await self._move_mouse(page)
            
            # Get initial scroll position
            initial_position = await page.evaluate('window.scrollY')
            
            # Get page dimensions
            metrics = await page.evaluate('''() => {
                return {
                    height: document.documentElement.scrollHeight,
                    viewportHeight: window.innerHeight,
                    availableScroll: document.documentElement.scrollHeight - window.innerHeight
                }
            }''')
            
            if metrics['availableScroll'] <= 0:
                if self.verbose:
                    print("Page too short to scroll")
                return

            # Calculate target scroll position (between 30% and 70% of available scroll)
            available_scroll = metrics['availableScroll']
            target_scroll = random.randint(
                int(available_scroll * 0.3),
                int(available_scroll * 0.7)
            )
            
            # Scroll in smaller increments
            current_position = 0
            while current_position < target_scroll:
                # Scroll 300-400 pixels at a time
                increment = random.randint(300, 400)
                next_position = min(current_position + increment, target_scroll)
                
                # Perform the scroll
                await page.evaluate(f'''() => {{
                    window.scrollTo({{
                        top: {next_position},
                        behavior: "smooth"
                    }});
                }}''')
                
                # Even shorter wait between scrolls
                await asyncio.sleep(random.uniform(0.2, 0.4))
                current_position = next_position

        except Exception as e:
            if self.verbose:
                print(f"Error during scrolling: {e}")

    async def _attempt_clicking(self, page: Page):
        """Attempt to click on some safe elements"""
        try:
            safe_selectors = [
                'button:not([type="submit"])',
                'a[href^="#"]',
                '.tab',
                '[role="tab"]',
                '.accordion',
                '[aria-expanded]'
            ]

            for selector in random.sample(safe_selectors, len(safe_selectors)):
                try:
                    is_visible = await page.is_visible(selector, timeout=1000)
                    if is_visible:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            element = random.choice(elements)
                            await element.click(timeout=1000)
                            await asyncio.sleep(random.uniform(0.3, 0.5))
                            break
                except Exception:
                    continue

        except Exception as e:
            if self.verbose:
                print(f"Error during clicking: {e}") 