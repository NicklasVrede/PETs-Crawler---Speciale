import os
import json
from collections import defaultdict, Counter
import pprint

def explore_json_structure(json_file, max_items=3, max_depth=3):
    """Explore the structure of a JSON file and extract all available features"""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Top-level keys
    print(f"\n=== TOP LEVEL KEYS IN {os.path.basename(json_file)} ===")
    for key in data.keys():
        print(f"- {key}")
    
    # Recursive function to explore structure
    def explore_structure(obj, prefix="", depth=0, max_depth=max_depth):
        if depth > max_depth:
            return f"{type(obj).__name__}... (max depth reached)"
        
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            
            result = "{\n"
            for i, (k, v) in enumerate(obj.items()):
                if i >= max_items and len(obj) > max_items + 1:
                    result += f"{prefix}  ... ({len(obj) - max_items} more keys)\n"
                    break
                result += f"{prefix}  '{k}': {explore_structure(v, prefix + '  ', depth + 1, max_depth)},\n"
            result += f"{prefix}}}"
            return result
        
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            
            if all(not isinstance(x, (dict, list)) for x in obj):
                if len(obj) > max_items:
                    sample = obj[:max_items]
                    return f"{sample} ... ({len(obj)} items total)"
                return str(obj)
            
            result = "[\n"
            for i, item in enumerate(obj):
                if i >= max_items and len(obj) > max_items:
                    result += f"{prefix}  ... ({len(obj) - max_items} more items)\n"
                    break
                result += f"{prefix}  {explore_structure(item, prefix + '  ', depth + 1, max_depth)},\n"
            result += f"{prefix}]"
            return result
        
        else:
            return str(obj)
    
    # Explore each top-level section
    for key in data.keys():
        print(f"\n=== {key.upper()} STRUCTURE ===")
        structure = explore_structure(data[key])
        print(structure)
        
        # Special handling for common sections
        if key == 'banner_analysis':
            banner = data[key]
            
            if 'img_match' in banner:
                print("\nImage Match Analysis:")
                for visit_id in banner['img_match']:
                    print(f"  Visit: {visit_id}")
                    visit_data = banner['img_match'][visit_id]
                    for img_file, results in visit_data.items():
                        print(f"    {img_file}:")
                        for result_key, result_val in results.items():
                            print(f"      {result_key}: {result_val}")
            
            if 'text_match' in banner:
                print("\nText Match Analysis:")
                for visit_id in banner['text_match']:
                    print(f"  Visit: {visit_id}")
                    visit_data = banner['text_match'][visit_id]
                    for html_file, results in visit_data.items():
                        print(f"    {html_file}:")
                        for result_key, result_val in results.items():
                            print(f"      {result_key}: {result_val}")
            
            if 'page_loaded' in banner:
                print("\nPage Load Status:")
                for visit_id in banner['page_loaded']:
                    print(f"  Visit: {visit_id}")
                    visit_data = banner['page_loaded'][visit_id]
                    for file, status in visit_data.items():
                        print(f"    {file}: {status}")
        
        elif key == 'network_data':
            print("\nNetwork Data Summary:")
            for visit_id, visit_data in data[key].items():
                if 'requests' in visit_data:
                    requests = visit_data['requests']
                    print(f"  Visit {visit_id}: {len(requests)} requests")
                    
                    # Count request types
                    resource_types = Counter([req.get('resource_type') for req in requests if 'resource_type' in req])
                    if resource_types:
                        print("  Resource Types:")
                        for res_type, count in resource_types.most_common():
                            print(f"    - {res_type}: {count}")
                    
                    # Sample of domains
                    domains = [req.get('domain') for req in requests if 'domain' in req]
                    unique_domains = set(domains)
                    if unique_domains:
                        print(f"  Unique domains: {len(unique_domains)}")
                        print(f"  Sample domains: {list(unique_domains)[:5]}")
        
        elif key == 'cookies':
            print("\nCookies Summary:")
            if isinstance(data[key], dict):
                for visit_id, cookies in data[key].items():
                    print(f"  Visit {visit_id}: {len(cookies)} cookies")
                    if cookies:
                        print(f"  Cookie domains: {[c.get('domain') for c in cookies[:3]]}")
            elif isinstance(data[key], list):
                cookies = data[key]
                print(f"  Total cookies: {len(cookies)}")
                if cookies:
                    print(f"  Cookie domains: {[c.get('domain') for c in cookies[:3]]}")

def main():
    # Change this to your target JSON file
    json_file = "data/crawler_data/test/amazon.co.uk.json"
    
    if not os.path.exists(json_file):
        print(f"Error: File not found: {json_file}")
        return
    
    print(f"Analyzing JSON structure for: {json_file}")
    explore_json_structure(json_file)
    
    print("\nAnalysis complete! You now have a better understanding of available features.")

if __name__ == "__main__":
    main() 