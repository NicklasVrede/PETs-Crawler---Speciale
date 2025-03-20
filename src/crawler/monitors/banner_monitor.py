import os
import json
from datetime import datetime
import asyncio
from pathlib import Path

class BannerMonitor:
    def __init__(self, data_dir="data/banner_data", verbose=False):
        self.screenshot_dir = os.path.join(data_dir, "screenshots")
        self.html_dir = os.path.join(data_dir, "html")
        self.verbose = verbose
        self.captures = []
        
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
            return
            
        try:
            # Create domain-specific directories
            domain_screenshot_dir = os.path.join(self.screenshot_dir, self.domain)
            domain_html_dir = os.path.join(self.html_dir, self.domain)
            Path(domain_screenshot_dir).mkdir(exist_ok=True)
            Path(domain_html_dir).mkdir(exist_ok=True)
            
            # Use simplified filenames
            filename = f"visit{self.visit_number}_{self.extension_name}"
            
            # Capture screenshot
            screenshot_path = os.path.join(domain_screenshot_dir, f"{filename}.png")
            await page.screenshot(path=screenshot_path, full_page=False)
            
            # Capture HTML
            html_path = os.path.join(domain_html_dir, f"{filename}.html")
            html_content = await page.content()
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Capture basic metadata
            metadata = {
                "url": page.url,
                "title": await page.title(),
                "domain": self.domain,
                "visit": self.visit_number,
                "extension": self.extension_name,
                "screenshot_path": screenshot_path,
                "html_path": html_path
            }
            
            self.captures.append(metadata)
            
            if self.verbose:
                print(f"Captured subpage for {self.domain}: {filename}")
                
            # Mark this specific visit as complete
            self.completed_visits.add(visit_key)
                
        except Exception as e:
            if self.verbose:
                print(f"Error capturing subpage: {e}")
    
    def get_capture_data(self):
        """Return all captured data info"""
        return self.captures
        
    def save_capture_index(self, output_dir=None):
        """Save an index of all captures for easy lookup"""
        if not output_dir:
            output_dir = os.path.dirname(self.screenshot_dir)
        
        # Group captures by domain
        captures_by_domain = {}
        for capture in self.captures:
            domain = capture['domain']
            if domain not in captures_by_domain:
                captures_by_domain[domain] = []
            captures_by_domain[domain].append(capture)
        
        # Save one index file per domain
        index_files = []
        for domain, domain_captures in captures_by_domain.items():
            # Create domain directory in the output_dir if it doesn't exist
            domain_dir = os.path.join(output_dir, domain)
            Path(domain_dir).mkdir(exist_ok=True)
            
            # Save an index file in the domain directory
            index_path = os.path.join(domain_dir, f"capture_index.json")
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(domain_captures, f, indent=2)
            
            index_files.append(index_path)
            
            if self.verbose:
                print(f"Saved capture index for {domain} to {index_path}")
        
        return index_files 