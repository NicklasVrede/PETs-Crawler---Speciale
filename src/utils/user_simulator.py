import random
import asyncio
from playwright.async_api import Page
from tqdm import tqdm

class UserSimulator:
    """Class to simulate realistic user behavior during web browsing"""
    
    def __init__(self, seed=None, verbose=False):
        """Initialize the simulator with configurable parameters"""
        self.random = random.Random(seed)
        self.verbose = verbose
        
    def _log(self, message):
        """Helper method for debug logging"""
        if self.verbose:
            tqdm.write(f"UserSim: {message}")
            
    async def simulate_interaction(self, page: Page, url=None):
        """Simulate realistic user interaction on the page"""
        try:
            # If URL is provided, use it to create a deterministic seed for this page
            if url:
                # Create a page-specific random generator with a consistent seed for the same URL
                page_seed = hash(url) % 10000
                page_random = random.Random(page_seed)
                self._log(f"URL: {url} -> Using deterministic seed: {page_seed}")
            else:
                # Fallback to the instance random generator
                page_random = self.random
                self._log(f"No URL provided, using instance random generator")
                

            # Deterministic scrolling based on URL
            self._log("Starting scrolling simulation")
            await self._perform_scrolling(page, page_random, url)

            # No clicking - we've removed this for better determinism
            self._log("Scrolling complete - user simulation finished")

        except Exception as e:
            tqdm.write(f"Error during user simulation: {e}")

    async def _move_mouse(self, page: Page, x_percent: float, y_percent: float):
        """Move mouse to a position specified by percentage of viewport dimensions"""
        try:
            # Check if page is still valid before evaluating
            if not page.is_closed():
                viewport_size = await page.evaluate('''() => {
                    return {
                        width: window.innerWidth || 1000,
                        height: window.innerHeight || 800
                    }
                }''', timeout=1000)  # Add timeout to avoid hanging
                
                x_pos = int(viewport_size['width'] * x_percent)
                y_pos = int(viewport_size['height'] * y_percent)
                
                self._log(f"Moving mouse to absolute position: ({x_pos}, {y_pos})")
                await page.mouse.move(x_pos, y_pos)
            else:
                self._log("Page is closed, skipping mouse movement")
                
        except Exception as e:
            # Just log the error and continue - don't let mouse errors break the flow
            self._log(f"Error moving mouse (continuing anyway): {str(e)}")
            # Use default position if we couldn't calculate properly
            try:
                if not page.is_closed():
                    await page.mouse.move(500, 400)  # Move to a reasonable default position
            except:
                pass  # Ignore errors in the fallback too

    async def _perform_scrolling(self, page: Page, page_random, url=None):
        """Perform deterministic scrolling actions based on URL"""
        try:
            # Calculate deterministic positions based on URL/page_random
            scroll_percentage = 0.4 + (page_random.random() * 0.2)  # 40-60%
            mouse_x = 0.3 + (page_random.random() * 0.4)  # 30-70%
            mouse_y = 0.2 + (page_random.random() * 0.6)  # 20-80%
            
            self._log(f"Deterministic values: scroll_percentage={scroll_percentage:.4f}, mouse_x={mouse_x:.4f}, mouse_y={mouse_y:.4f}")
            
            # Move mouse to deterministic position
            self._log(f"Moving mouse to relative position ({mouse_x:.4f}, {mouse_y:.4f})")
            await self._move_mouse(page, mouse_x, mouse_y)
            
            # Get page dimensions - wrap this in a try-except
            metrics = None
            try:
                metrics = await page.evaluate('''() => {
                    // Add checks for documentElement and body existence
                    const docEl = document.documentElement;
                    const body = document.body;
                    if (!docEl && !body) return null; // Cannot get dimensions

                    const height = Math.max(
                        body?.scrollHeight ?? 0,
                        docEl?.scrollHeight ?? 0,
                        body?.offsetHeight ?? 0,
                        docEl?.offsetHeight ?? 0,
                        body?.clientHeight ?? 0,
                        docEl?.clientHeight ?? 0
                    );
                    const viewportHeight = window.innerHeight || (docEl ? docEl.clientHeight : 0);

                    return {
                        height: height,
                        viewportHeight: viewportHeight,
                        availableScroll: Math.max(0, height - viewportHeight) // Ensure non-negative
                    };
                }''')
                # Check if evaluate returned null due to missing elements
                if metrics is None:
                    self._log("Could not determine page dimensions (document elements missing?), skipping scroll.")
                    return

            except Exception as e:
                # Catch errors during dimension evaluation (like the scrollHeight error)
                self._log(f"Could not evaluate page dimensions: {e}. Skipping scroll.")
                # Optionally check if the specific error occurred:
                # if "scrollHeight" in str(e):
                #     self._log("Encountered scrollHeight error, skipping scroll.")
                return # Skip scrolling if dimensions can't be determined

            self._log(f"Page metrics: height={metrics['height']}, viewportHeight={metrics['viewportHeight']}, availableScroll={metrics['availableScroll']}")
            
            if metrics['availableScroll'] <= 0:
                self._log("Page has no scrollable content, skipping scroll")
                return

            # Calculate target scroll position based on predetermined percentage
            available_scroll = metrics['availableScroll']
            target_scroll = int(available_scroll * scroll_percentage)
            
            self._log(f"Target scroll: {target_scroll}px ({scroll_percentage*100:.1f}% of available scroll)")
            
            # Fixed scroll increment
            increment = 300
            
            # Pre-calculate the exact number of steps needed
            steps = (target_scroll + increment - 1) // increment  # ceiling division
            
            self._log(f"Will scroll in {steps} steps with {increment}px increment")
            
            # Perform deterministic scrolling with exactly the right number of steps
            for step in range(steps):
                next_position = min((step + 1) * increment, target_scroll)
                
                self._log(f"Scroll step {step+1}/{steps}: scrolling to {next_position}px")
                
                # First try the smooth scrolling method
                smooth_scroll_succeeded = False
                try:
                    # Remove the unsupported 'timeout' argument
                    await page.evaluate(f'''() => {{
                        window.scrollTo({{
                            top: {next_position},
                            behavior: "smooth"
                        }});
                    }}''')
                    # If evaluate succeeds, assume smooth scroll was initiated
                    smooth_scroll_succeeded = True
                    self._log("Smooth scroll initiated via evaluate.")
                    await asyncio.sleep(0.5) # Give animation 0.5s

                except Exception as e:
                    error_type = type(e).__name__
                    self._log(f"Smooth scrolling failed ({error_type}: {e}), falling back to wheel.")


                # If smooth scroll failed, use the fallback
                if not smooth_scroll_succeeded:
                    # Fall back to Playwright's mouse wheel method
                    scroll_amount = increment  # How much to scroll in this step
                    # Ensure page is still valid before wheel action
                    if not page.is_closed():
                        try:
                            # Add a timeout around the wheel action
                            scroll_timeout = 2.0 # seconds
                            await asyncio.wait_for(
                                page.mouse.wheel(0, scroll_amount),
                                timeout=scroll_timeout
                            )
                        except asyncio.TimeoutError:
                            tqdm.write(f"Mouse wheel action timed out after {scroll_timeout}s. Stopping scroll for this page.")
                            break # Exit scroll loop if wheel times out
                        except Exception as wheel_err:
                            tqdm.write(f"Error during mouse wheel action: {wheel_err}. Stopping scroll for this page.")
                            break # Exit scroll loop on other wheel errors
                    else:
                        tqdm.write("Page closed during scroll fallback, stopping scroll.")
                        break # Exit scroll loop if page closed
                
                # Fixed wait between scrolls
                await asyncio.sleep(0.3)

            self._log(f"Scrolling complete, reached target {target_scroll}px")

        except Exception as e:
            # Catch any other unexpected error during the scrolling process
            tqdm.write(f"Error during scrolling simulation: {e}") 