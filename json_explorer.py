import os
import json
from collections import defaultdict, Counter
import pprint

def explore_json_structure(json_file):
    """Explore the structure of a JSON file and extract all available features"""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Top-level keys
    print(f"\n=== TOP LEVEL KEYS IN {os.path.basename(json_file)} ===")
    for key in data.keys():
        print(f"- {key}")
    
    # Explore cookie_analysis structure if available
    if 'cookie_analysis' in data:
        print("\n=== COOKIE ANALYSIS STRUCTURE ===")
        cookie_analysis = data['cookie_analysis']
        print("Keys:", list(cookie_analysis.keys()))
        
        if 'categories' in cookie_analysis:
            print("\nCookie Categories:")
            for category, count in cookie_analysis['categories'].items():
                print(f"  - {category}: {count}")
    
    # Explore domain_stats structure if available
    if 'domain_stats' in data:
        print("\n=== DOMAIN STATS STRUCTURE ===")
        domain_stats = data['domain_stats']
        print("Keys:", list(domain_stats.keys()))
        
        if 'statistics' in domain_stats:
            print("\nStatistics Keys:", list(domain_stats['statistics'].keys()))
            
            if 'categories' in domain_stats['statistics']:
                print("\nDomain Categories:")
                for category, count in domain_stats['statistics']['categories'].items():
                    print(f"  - {category}: {count}")
    
    # Explore visits structure for the first visit
    if 'visits' in data and data['visits']:
        print("\n=== FIRST VISIT STRUCTURE ===")
        first_visit = data['visits'][0]
        print("Visit Keys:", list(first_visit.keys()))
        
        # Network requests sample
        if 'network' in first_visit and 'requests' in first_visit['network']:
            requests = first_visit['network']['requests']
            if requests:
                print(f"\nSample Request Keys ({len(requests)} total requests):", list(requests[0].keys()))
                
                # Count resource types
                resource_types = Counter([req.get('resource_type') for req in requests if 'resource_type' in req])
                print("\nResource Types:")
                for res_type, count in resource_types.most_common():
                    print(f"  - {res_type}: {count}")
    
    # Explore cookies structure
    if 'cookies' in data:
        print("\n=== COOKIES STRUCTURE ===")
        cookies = data['cookies']
        print("Visit Numbers with Cookies:", list(cookies.keys()))
        
        # Get a sample cookie if available
        for visit_num, visit_cookies in cookies.items():
            if visit_cookies:
                print(f"\nSample Cookie Keys (from visit {visit_num}):", list(visit_cookies[0].keys()))
                break
    
    # Explore fingerprinting structure if available
    if 'fingerprinting' in data:
        print("\n=== FINGERPRINTING STRUCTURE ===")
        fingerprinting = data['fingerprinting']
        print("Keys:", list(fingerprinting.keys()))
        
        if 'all_visits' in fingerprinting and fingerprinting['all_visits']:
            first_fp_data = fingerprinting['all_visits'][0]
            print("\nFingerprinting Visit Data Keys:", list(first_fp_data.keys()))
            
            if 'category_breakdown' in first_fp_data:
                print("\nCategory Breakdown:", first_fp_data['category_breakdown'])

def main():
    # Change this to your target JSON file
    json_file = "data/crawler_data/i_dont_care_about_cookies/Active.com.json"
    
    if not os.path.exists(json_file):
        print(f"Error: File not found: {json_file}")
        return
    
    print(f"Analyzing JSON structure for: {json_file}")
    explore_json_structure(json_file)
    
    print("\nAnalysis complete! You now have a better understanding of available features.")

if __name__ == "__main__":
    main() 