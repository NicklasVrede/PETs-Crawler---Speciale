import json
from pathlib import Path
from playwright.async_api import async_playwright
import asyncio
from analyzers.fingerprint_collector import FingerprintCollector

class ScriptAnalyzer:
    async def setup_browser(self):
        """Setup Playwright browser"""
        print("Setting up browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.collector = FingerprintCollector()

    async def analyze_script(self, script_content: str, script_url: str):
        """Analyze a single script using the fingerprint collector"""
        # Create a fresh page for each script
        page = await self.context.new_page()
        
        try:
            # Setup monitoring
            await self.collector.inject_monitors(page)
            
            # Analyze the script
            result = await self.collector.analyze_script(page, script_content, script_url)
            return result
            
        finally:
            await page.close()

    async def analyze_scripts(self, json_file_path):
        """Analyze JavaScript scripts in a site's data file for fingerprinting"""
        print(f"\nAnalyzing scripts from {json_file_path}")
        
        # Setup browser if needed
        if not hasattr(self, 'browser'):
            await self.setup_browser()
        
        # Load site data
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        fingerprinting_scripts = []
        
        # Analyze each script
        for script in data.get('scripts', []):
            try:
                result = await self.analyze_script(script['content'], script['url'])
                
                if result['fingerprinting_detected']:
                    fingerprinting_scripts.append({
                        'url': script['url'],
                        'page_url': script['page_url'],
                        'timestamp': script['timestamp'],
                        'api_calls': result['api_calls'],
                        'statistics': result['statistics']
                    })
                    print(f"Found fingerprinting in {script['url']}")
                    print(f"API calls: {len(result['api_calls'])}")
            
            except Exception as e:
                print(f"Error analyzing script {script['url']}: {e}")
        
        # Add analysis results to the JSON file
        data['fingerprinting_analysis'] = {
            'total_scripts_analyzed': len(data.get('scripts', [])),
            'fingerprinting_scripts_found': len(fingerprinting_scripts),
            'fingerprinting_scripts': fingerprinting_scripts
        }
        
        # Save updated JSON
        with open(json_file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return fingerprinting_scripts

    async def cleanup(self):
        """Clean up browser resources"""
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop() 