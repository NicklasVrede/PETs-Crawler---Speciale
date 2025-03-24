import sys
import os
sys.path.append('.')  # Make sure the root directory is in the path

from src.managers.ghostery_manager import GhosteryManager
import json

def test_ghostery_directly():
    """Test the GhosteryManager directly to isolate issues"""
    
    # Create ghostery manager instance
    ghostery = GhosteryManager()
    
    test_urls = [
        "https://www.google-analytics.com",
        "doubleclick.net", 
        "connect.facebook.net",
        "analytics.twitter.com",
        "https://js.hs-scripts.com",
        "assets.adobedtm.com",
        "js.clicktale.net", 
        "cdn.optimizely.com",
        "cdn.cloudflare.net",
        "akamaiedge.net",
        "d1af033869koo7.cloudfront.net",
        "amazon-adsystem.com",
        "https://bat.bing.com",
        "pixel.facebook.com",
        "https://static.hotjar.com"
    ]
    
    print("Testing Ghostery manager directly:")
    print("-" * 50)
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        
        # For URLs without protocol, test both with and without adding https://
        if not (url.startswith('http://') or url.startswith('https://')):
            print(f"Testing original: {url}")
            result1 = ghostery.analyze_request(url)
            print(f"Has matches: {bool(result1.get('matches'))}")
            
            with_https = f"https://{url}"
            print(f"Testing with https: {with_https}")
            result2 = ghostery.analyze_request(with_https)
            print(f"Has matches: {bool(result2.get('matches'))}")
            
            # Compare which approach works better
            if result1.get('matches') and not result2.get('matches'):
                print("❗ Original URL works better")
            elif not result1.get('matches') and result2.get('matches'):
                print("❗ Adding https:// works better")
        else:
            # URL already has protocol
            result = ghostery.analyze_request(url)
            print(f"Has matches: {bool(result.get('matches'))}")
        
        # Show detailed results for debugging
        result = ghostery.analyze_request(url)
        if result.get('matches'):
            print(f"✅ Matches found: {len(result['matches'])}")
            for match in result['matches']:
                print(f"  - {match['organization']['name']} / {match['category']['name']}")
        else:
            print("❌ No matches found")
            
            # Debug the raw output
            print(f"Raw result: {json.dumps(result, indent=2)[:200]}...")
    
    print("\nTest complete")

def inspect_ghostery_bridge():
    """Inspect the Ghostery bridge implementation"""
    bridge_file = os.path.join('src', 'managers', 'ghostery_bridge.js')
    
    if not os.path.exists(bridge_file):
        print(f"Bridge file not found: {bridge_file}")
        return
    
    print("\nInspecting Ghostery bridge file:")
    print("-" * 50)
    
    with open(bridge_file, 'r') as f:
        content = f.read()
        print(content)
        
    print("\nBridge file inspection complete")

if __name__ == "__main__":
    test_ghostery_directly()
    inspect_ghostery_bridge() 