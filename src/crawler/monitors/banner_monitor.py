import os
from pathlib import Path


class BannerMonitor:
    def __init__(self, data_dir="data/banner_data", verbose=False):
        self.screenshot_dir = os.path.join(data_dir, "screenshots")
        self.html_dir = os.path.join(data_dir, "html")
        self.verbose = verbose
        
        # Track completion by visit instead of a single flag
        self.completed_visits = set()
        
        # Ensure directories exist
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        Path(self.html_dir).mkdir(parents=True, exist_ok=True)
        
    async def setup_monitoring(self, page, domain, visit_number, extension_name=None):
        """Initialize monitoring"""
        # Store context for naming
        self.domain = domain
        self.visit_number = visit_number
        self.extension_name = extension_name or "no_extension"
        
    async def capture_on_subpage(self, page, domain=None, visit_number=None, extension_name=None):
        """Capture data when visiting a subpage"""  
        # Update state and check if already captured
        if not self._update_state(domain, visit_number, extension_name):
            return
            
        try:
            # Prepare paths and filenames
            paths = self._prepare_paths()
            
            # Capture and save data
            await self._save_capture(page, paths)
                
        except Exception as e:
            if self.verbose:
                print(f"Error capturing subpage: {e}")
    
    def _update_state(self, domain, visit_number, extension_name):
        """Update state variables and check if already captured"""
        # Update values if provided
        if domain:
            self.domain = domain
        if visit_number is not None:
            self.visit_number = visit_number
        if extension_name:
            self.extension_name = extension_name
        
        if self.verbose:
            print(f"Capturing subpage for {self.domain}")
            
        # Check if we've already completed this specific visit
        visit_key = f"{self.domain}_{self.visit_number}_{self.extension_name}"
        if visit_key in self.completed_visits:
            if self.verbose:
                print(f"Visit {self.visit_number} for {self.domain} already captured, skipping")
            return False
        
        return True
    
    def _prepare_paths(self):
        """Create directories and prepare file paths"""
        # Create domain-specific directories
        domain_screenshot_dir = os.path.join(self.screenshot_dir, self.domain)
        domain_html_dir = os.path.join(self.html_dir, self.domain)
        Path(domain_screenshot_dir).mkdir(exist_ok=True)
        Path(domain_html_dir).mkdir(exist_ok=True)
        
        # Use simplified filenames
        filename = f"visit{self.visit_number}_{self.extension_name}"
        screenshot_path = os.path.join(domain_screenshot_dir, f"{filename}.png")
        html_path = os.path.join(domain_html_dir, f"{filename}.html")
        
        return {
            'filename': filename,
            'screenshot_path': screenshot_path,
            'html_path': html_path
        }
    
    async def _save_capture(self, page, paths):
        """Save screenshot and HTML"""
        # Capture screenshot
        await page.screenshot(path=paths['screenshot_path'], full_page=False)
        
        # Capture HTML
        html_content = await page.content()
        with open(paths['html_path'], 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        if self.verbose:
            print(f"Captured subpage for {self.domain}: {paths['filename']}")
            
        # Mark this specific visit as complete
        visit_key = f"{self.domain}_{self.visit_number}_{self.extension_name}"
        self.completed_visits.add(visit_key)