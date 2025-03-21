#!/usr/bin/env python3
"""
Test fingerprinting detection on a local test page.
"""

import asyncio
import os
import json
from pathlib import Path
from playwright.async_api import async_playwright

from monitors.fingerprint_collector import FingerprintCollector

async def test_fingerprinting():
    """Test fingerprinting detection on a local HTML file."""
    # Path to test HTML file
    test_file = Path(__file__).parent / "test_fingerprinting.html"
    if not test_file.exists():
        print(f"Error: Test file not found at {test_file}")
        return
    
    file_url = f"file://{test_file.absolute()}"
    print(f"Testing fingerprinting detection on: {file_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Create fingerprint collector with verbose mode
        collector = FingerprintCollector(verbose=True)
        
        # Add handler for console messages to see JavaScript debug output
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        
        # Set up monitoring
        await collector.setup_monitoring(page, visit_number=0)
        
        # Verify monitoring by directly triggering a few calls in JavaScript
        print("\nVerifying monitoring setup...")
        await page.evaluate("""
            console.log("Running direct monitoring verification");
            // Accessing navigator.userAgent
            const ua = navigator.userAgent; 
            console.log("UserAgent: " + ua.substring(0, 20) + "...");
            
            // Creating a canvas
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.fillText("Test", 10, 10);
            const dataURL = canvas.toDataURL();
            console.log("Created test canvas");
        """)
        
        # Wait for monitoring to process these calls
        await page.wait_for_timeout(1000)
        
        print("\nVerification results before page load:")
        pre_results = collector.get_fingerprinting_data()
        # Access the visit 0 data directly instead of summary
        visit_data = pre_results.get(0, {})
        detected = visit_data.get("fingerprinting_detected", False)
        techniques = visit_data.get("techniques_detected", [])
        print(f"Fingerprinting detected: {detected}")
        print(f"Techniques detected: {techniques}")
        
        # Navigate to the test page
        await page.goto(file_url)
        
        # Force run all tests by clicking the button
        try:
            await page.click('button:has-text("Run All Fingerprinting Tests")')
            print("Successfully triggered all fingerprinting tests")
        except Exception as e:
            print(f"Failed to trigger tests: {e}")
            
            # Try to run tests directly through JavaScript as fallback
            try:
                await page.evaluate("runAllTests()")
                print("Successfully ran tests through JavaScript evaluation")
            except Exception as e2:
                print(f"Failed to run tests through evaluation: {e2}")
        
        # Wait longer for all fingerprinting tests to complete
        await page.wait_for_timeout(5000)
        
        # Try to extract console output
        logs = await page.evaluate("""() => {
            let results = document.getElementById('results');
            return results ? results.textContent : 'No results found';
        }""")
        print("\nTest page results:")
        print(logs)
        
        # Get results
        results = collector.get_fingerprinting_data()
        
        # Print detection results
        print("\n=== Fingerprinting Detection Results ===")
        # Access visit 0 data directly
        visit_data = results.get(0, {})
        detected = visit_data.get("fingerprinting_detected", False)
        techniques = visit_data.get("techniques_detected", [])
        print(f"Fingerprinting detected: {detected}")
        print(f"Techniques detected: {techniques}")
        
        # Print category counts if available
        if "domain_summary" in visit_data and "category_breakdown" in visit_data["domain_summary"]:
            print("\n=== Category Counts ===")
            for category, count in visit_data["domain_summary"]["category_breakdown"].items():
                print(f"{category}: {count}")
        
        # API breakdown
        print("\n=== API Calls ===")
        
        # Access domain level API breakdown
        if "domain_summary" in visit_data and "api_breakdown" in visit_data["domain_summary"]:
            api_breakdown = visit_data["domain_summary"]["api_breakdown"]
            for api, count in api_breakdown.items():
                if count > 0:
                    print(f"{api}: {count}")
        else:
            print("No API breakdown available in visit data")
        
        # Print the full structure for debugging
        print("\n=== Complete Results Structure ===")
        print(json.dumps(results, indent=2, default=str))
        
        #await browser.close()

if __name__ == "__main__":
    asyncio.run(test_fingerprinting()) 