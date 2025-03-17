import random
import asyncio
from playwright.async_api import Page
from urllib.parse import urlparse
from tqdm import tqdm

class UserSimulator:
    def __init__(self, verbose=False):
        self.scroll_probability = 0.7
        self.click_probability = 0.3
        self.max_scroll_attempts = 2
        self.max_click_attempts = 1
        self.verbose = verbose

    async def simulate_interaction(self, page, base_domain=None):
        """Simulate natural user behavior on the page with balanced adaptive scrolling"""
        try:
            # Reasonable initial wait - not too long, not too short
            initial_wait = random.uniform(0.5, 1.0)  # Reduced from 1.0-2.0
            await asyncio.sleep(initial_wait)
            
            # Get total scroll height and content metrics
            scroll_metrics = await page.evaluate('''() => {
                return {
                    scrollHeight: document.body.scrollHeight,
                    textDensity: document.body.innerText.length / (document.body.scrollHeight || 1),
                    imageCount: document.querySelectorAll('img').length,
                    isArticle: !!document.querySelector('article') || 
                               document.querySelectorAll('p').length > 10
                }
            }''')
            
            max_scroll = scroll_metrics['scrollHeight']
            scroll_amount = 0
            
            # Extract domain for homepage check
            current_url = page.url
            parsed_url = urlparse(current_url)
            current_domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Determine scroll depth based on content type
            is_article = scroll_metrics.get('isArticle', False)
            is_image_heavy = scroll_metrics.get('imageCount', 0) > 8
            is_homepage = base_domain and current_domain == base_domain and parsed_url.path in ['/', '']
            
            # Determine scroll percentage - keep this part adaptive
            if is_homepage:
                scroll_percentage = random.uniform(0.4, 0.7)  # Slightly reduced
            elif is_article:
                scroll_percentage = random.uniform(0.6, 0.8)  # Slightly reduced
            else:
                scroll_percentage = random.uniform(0.3, 0.5)  # Slightly reduced
            
            target_scroll = int(max_scroll * scroll_percentage)
            
            if self.verbose:
                tqdm.write(f"Scrolling {int(scroll_percentage * 100)}% of page ({target_scroll}px)")
            
            # Quick mouse movement
            viewport = page.viewport_size
            middle_x = viewport['width'] // 2
            middle_y = viewport['height'] // 2
            await page.mouse.move(middle_x, middle_y, steps=2)
            
            # Faster adaptive scrolling based on content
            if is_article:
                # Medium speed for articles
                scroll_increment = random.randint(100, 150)  # Increased
                scroll_pause = random.uniform(0.1, 0.2)  # Decreased
            elif is_image_heavy:
                # Medium-fast for image galleries
                scroll_increment = random.randint(120, 200)  # Increased
                scroll_pause = random.uniform(0.08, 0.15)  # Decreased
            else:
                # Fast for general browsing
                scroll_increment = random.randint(150, 250)  # Increased
                scroll_pause = random.uniform(0.05, 0.1)  # Decreased
            
            # Scroll down
            while scroll_amount < target_scroll:
                next_increment = min(scroll_increment, target_scroll - scroll_amount)
                if next_increment <= 0:
                    break
                    
                # Scroll
                await page.mouse.wheel(0, next_increment)
                scroll_amount += next_increment
                
                # Brief pause with less variation
                await asyncio.sleep(scroll_pause * random.uniform(0.9, 1.1))
                
                # Reduced chance of mouse movement (70% → 30%)
                if random.random() > 0.7:
                    await page.mouse.move(
                        middle_x + random.randint(-200, 200),
                        middle_y + random.randint(-100, 100),
                        steps=2
                    )
                    
                # Reduced chance and duration of reading pauses (10% → 5%)
                if random.random() > 0.95:
                    await asyncio.sleep(random.uniform(0.3, 0.6))  # Shorter pauses
            
            # Shorter pause at end
            await asyncio.sleep(random.uniform(0.2, 0.5))  # Reduced
            
            # Reduce chance to scroll back to top (30% → 20%)
            if random.random() < 0.2:
                await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
                await asyncio.sleep(0.2)
            
        except Exception as e:
            tqdm.write(f"Scroll error: {str(e)}")

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