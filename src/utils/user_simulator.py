import random
import asyncio
from playwright.async_api import Page

class UserSimulator:
    def __init__(self):
        self.scroll_probability = 0.7
        self.click_probability = 0.3
        self.max_scroll_attempts = 2
        self.max_click_attempts = 1

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
            print(f"Error during user simulation: {e}")

    async def _perform_scrolling(self, page: Page):
        """Perform some scrolling actions"""
        try:
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
                print("Page too short to scroll")
                return

            # Always do at least one scroll
            scroll_attempts = random.randint(1, self.max_scroll_attempts)
            
            for i in range(scroll_attempts):
                # Calculate next scroll position (between 30% and 70% of available scroll)
                available_scroll = metrics['availableScroll']
                scroll_amount = random.randint(
                    int(available_scroll * 0.3),
                    int(available_scroll * 0.7)
                )
                
                # Perform the scroll
                await page.evaluate(f'''() => {{
                    window.scrollTo({{
                        top: {scroll_amount},
                        behavior: "smooth"
                    }});
                }}''')
                
                # Short wait for scroll to complete
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # Verify scroll happened
                new_position = await page.evaluate('window.scrollY')
                if new_position == initial_position:
                    print("Scroll didn't change position")
                    break

        except Exception as e:
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
            print(f"Error during clicking: {e}") 