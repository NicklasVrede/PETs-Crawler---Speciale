#!/usr/bin/env python3
import json
import sys
import os
from collections import defaultdict

def is_numeric_key(key):
    """Check if a key is numeric (visit ID) or follows 'visitX' pattern"""
    if isinstance(key, str):
        if key.isdigit():
            return True
        if key.startswith('visit') and key[5:].isdigit():
            return True
    return isinstance(key, int)

def are_similar_dicts(d1, d2, tolerance=0.9):
    """Check if two dictionaries have similar keys and values"""
    if not (isinstance(d1, dict) and isinstance(d2, dict)):
        return False
    
    if not d1 or not d2:
        return False
        
    # Check key overlap
    keys1 = set(d1.keys())
    keys2 = set(d2.keys())
    common_keys = keys1.intersection(keys2)
    
    # If less than 70% keys match, they're different
    if len(common_keys) < min(len(keys1), len(keys2)) * 0.7:
        return False
        
    # For numeric values, check if they're similar
    similarity_count = 0
    for k in common_keys:
        if isinstance(d1[k], (int, float)) and isinstance(d2[k], (int, float)):
            # Values are considered similar if within 10% of each other
            if d1[k] == 0 and d2[k] == 0:
                similarity_count += 1
            elif d1[k] != 0 and d2[k] != 0:
                ratio = d1[k] / d2[k] if d2[k] != 0 else d2[k] / d1[k]
                if 0.9 <= ratio <= 1.1:
                    similarity_count += 1
    
    # If 90% of common keys have similar values, dictionaries are similar
    return similarity_count >= len(common_keys) * tolerance

def merge_dicts(d1, d2):
    """Merge two dictionaries, keeping all unique keys"""
    result = d1.copy()
    for k, v in d2.items():
        if k in result:
            if isinstance(result[k], dict) and isinstance(v, dict):
                # Recursively merge nested dictionaries
                result[k] = merge_dicts(result[k], v)
            # Don't override existing values for other types
        else:
            # Add new keys
            result[k] = v
    return result

def generate_json_skeleton(obj, parent_key=None, path=""):
    """
    Generate a JSON skeleton with all unique features but no duplicates.
    Handles numeric keys (like visit IDs) specially.
    """
    # Special case for headers - just show the count
    if parent_key == "headers" or path.endswith(".headers"):
        if isinstance(obj, dict):
            return f"<{len(obj)} HTTP headers>"
    
    # Special case for api_breakdown - just show the count
    if parent_key == "api_breakdown" or path.endswith(".api_breakdown"):
        if isinstance(obj, dict):
            return f"<{len(obj)} API entries>"
    
    # Special case for fingerprinting data
    if (parent_key == "fingerprinting" or path.endswith(".fingerprinting")) and isinstance(obj, dict):
        if "technique_breakdown" in obj and "domain_summary" in obj and isinstance(obj["domain_summary"], dict):
            if "category_breakdown" in obj["domain_summary"]:
                if are_similar_dicts(obj["technique_breakdown"], obj["domain_summary"]["category_breakdown"]):
                    # Add a note about potential duplication
                    obj["_note"] = "Note: technique_breakdown and domain_summary.category_breakdown appear to contain similar data"
    
    if isinstance(obj, dict):
        # Check if we have a dictionary with numeric keys that might be visits
        has_numeric_keys = any(is_numeric_key(k) for k in obj.keys())
        
        # If parent is network_data, visits, etc and we have numeric keys, treat specially
        if parent_key in ('network_data', 'visits', 'fingerprinting', 'storage') and has_numeric_keys:
            # Find a sample key (preferably "1" for visit1)
            sample_key = next((k for k in obj if k == "1" or k == 1), None)
            if sample_key is None:
                sample_key = next(iter(obj))
                
            # Create a new dict with just the sample and "..." key
            return {
                "...": f"Visit identifier (total: {len(obj)} visits)",
                "sample_visit": generate_json_skeleton(obj[sample_key], "sample_visit", path + ".sample_visit")
            }
        
        # Regular dictionary processing
        result = {}
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            result[k] = generate_json_skeleton(v, k, new_path)
        return result
    
    elif isinstance(obj, list):
        if not obj:
            return []
        
        original_length = len(obj)
        
        # Just take one sample for all array types
        if original_length > 0:
            sample = obj[0]
            result = [generate_json_skeleton(sample, parent_key, path + "[i]")]
            
            # Add note about additional items if there are more than one
            if original_length > 1:
                result.append(f"... ({original_length-1} more items)")
                
            return result
        else:
            return []
    
    else:
        # For primitive types, represent with actual or typical values
        if isinstance(obj, str) and len(obj) > 50:
            return f"{obj[:47]}..."
        return obj

def process_visit_based_section(value, section_name):
    """Process any section with visit-based identifiers"""
    if isinstance(value, dict) and any(is_numeric_key(k) for k in value.keys()):
        visit_count = len(value)
        if visit_count > 0:
            # Choose a sample key - prefer "1" if available
            sample_key = next((k for k in value if k == "1" or k == 1), None)
            if sample_key is None:
                sample_key = next(iter(value))
                
            return {
                "...": f"Visit identifier (total: {visit_count} visits)",
                "sample_visit": generate_json_skeleton(value[sample_key], "sample_visit", f"{section_name}.sample_visit")
            }
    return generate_json_skeleton(value, section_name, section_name)

def process_json_with_visit_awareness(data):
    """Pre-process the JSON to handle visit-based structures consistently"""
    result = {}
    
    # Process each top-level key
    for key, value in data.items():
        if key in ('network_data', 'fingerprinting', 'visits', 'cookies', 'storage'):
            result[key] = process_visit_based_section(value, key)
        elif key == 'banner_analysis':
            # Special handling for banner_analysis which has nested visit keys
            result[key] = handle_banner_analysis(value)
        elif key == 'statistics' and isinstance(value, dict) and 'cookie_operations' in value:
            # Special handling for statistics.cookie_operations
            result_stats = generate_json_skeleton(value, 'statistics', 'statistics')
            if 'cookie_operations' in result_stats:
                result_stats['cookie_operations'] = process_visit_based_section(
                    value['cookie_operations'], 'statistics.cookie_operations')
            result[key] = result_stats
        else:
            # Normal processing for other keys
            result[key] = generate_json_skeleton(value, key, key)
    
    return result

def handle_banner_analysis(banner_data):
    """Special handler for banner_analysis section with nested visit identifiers"""
    result = {}
    
    for key, value in banner_data.items():
        result[key] = process_visit_based_section(value, f"banner_analysis.{key}")
    
    return result

# Add this helper function to explicitly look for cookie_operations in the data
def find_and_process_cookie_operations(data):
    """Ensure cookie_operations is properly processed"""
    if isinstance(data, dict) and 'cookie_operations' in data:
        print("Found cookie_operations in top level")
        cookie_ops = data['cookie_operations']
        
        if isinstance(cookie_ops, dict) and cookie_ops:
            visit_count = len(cookie_ops)
            # Choose visit "1" if available, otherwise take the first one
            keys = list(cookie_ops.keys())
            sample_key = "1" if "1" in keys else keys[0]
            
            return {
                "...": f"Visit identifier (total: {visit_count} visits)",
                "sample_visit": cookie_ops[sample_key]
            }
    
    return data.get('cookie_operations', {})

# Simple file input handling
if len(sys.argv) > 1:
    file_path = sys.argv[1]
else:
    # Default file path
    file_path = "data/crawler_data non-kameleo/test/Amazon.co.uk_enhanced.json"

try:
    print(f"Reading JSON file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process with visit awareness
    skeleton = process_json_with_visit_awareness(data)
    
    # Create output filename based on input
    base_name = os.path.basename(file_path)
    output_path = f"skeleton_{base_name}"
    
    # Save the skeleton to a file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(skeleton, f, indent=2, ensure_ascii=False)
    
    print(f"JSON skeleton saved to: {output_path}")
    
    # Check for fingerprinting duplication specifically
    if 'fingerprinting' in data and isinstance(data['fingerprinting'], dict):
        # Get a visit sample
        visit_key = next((k for k in data['fingerprinting'] if is_numeric_key(k)), None)
        if visit_key and isinstance(data['fingerprinting'][visit_key], dict):
            fp_data = data['fingerprinting'][visit_key]
            if ('technique_breakdown' in fp_data and 'domain_summary' in fp_data and 
                isinstance(fp_data['domain_summary'], dict) and 'category_breakdown' in fp_data['domain_summary']):
                
                tech = fp_data['technique_breakdown']
                cat = fp_data['domain_summary']['category_breakdown']
                
                if are_similar_dicts(tech, cat):
                    print("\nNOTE: Detected potential duplicate data:")
                    print("The 'technique_breakdown' and 'domain_summary.category_breakdown' structures")
                    print("contain similar data. You may want to investigate if they're intended to be different.")
    
    # Print small preview
    print("\nJSON Preview (first few lines):")
    output_json = json.dumps(skeleton, indent=2, ensure_ascii=False)
    lines = output_json.split('\n')
    preview_lines = lines[:20] + ['...'] if len(lines) > 20 else lines
    print('\n'.join(preview_lines))
    
except FileNotFoundError:
    print(f"Error: File not found: {file_path}")
except json.JSONDecodeError:
    print(f"Error: Invalid JSON in file: {file_path}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 