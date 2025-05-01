import os
import re
import json
from collections import defaultdict
from tqdm import tqdm
from pprint import pprint

def analyze_cookie_consent_text(directory, verbose=False):
    """
    Analyze HTML files to detect cookie consent text and compare between baseline and extensions
    """
    # Get all HTML files in the directory
    all_files = [f for f in os.listdir(directory) if f.endswith('.html')]
    
    # Separate no_extension files from others
    no_extension_files = [f for f in all_files if 'no_extension' in f]
    extension_files = [f for f in all_files if 'no_extension' not in f]
    
    if verbose:
        tqdm.write(f"Found {len(no_extension_files)} no_extension HTML files and {len(extension_files)} extension HTML files")
    
    # Initialize JSON structure with "html_check" key
    json_results = {
        "html_check": {}
    }
    
    # Group files by visit number for comparison
    visit_groups = defaultdict(lambda: {'no_extension': None, 'extensions': []})
    
    for file in no_extension_files:
        visit_match = re.search(r'visit(\d+)_no_extension', file)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['no_extension'] = file
    
    for file in extension_files:
        visit_match = re.search(r'visit(\d+)_', file)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['extensions'].append(file)
    
    # Cookie-related keywords to look for
    cookie_keywords = [
        "cookie", "consent", "accept", "reject", "decline", 
        "privacy", "gdpr", "settings", "preferences",
        "necessary", "functional", "analytics", "marketing",
        "all", "afslå", "acceptér", "alle", "cookies",
        "luk", "acceptér", "policy", "approve"
    ]
    
    # Compare each no_extension file with its corresponding extension files
    for visit_num, files in visit_groups.items():
        no_ext_file = files['no_extension']
        ext_files = files['extensions']
        
        if not no_ext_file:
            continue
            
        if verbose:
            tqdm.write(f"Analyzing HTML for Visit {visit_num}")
        
        # Initialize the visit entry in JSON
        json_results["html_check"][f"visit{visit_num}"] = {
            "keywords": [],
            "extensions": {}
        }
        
        # Process the no_extension HTML
        no_ext_path = os.path.join(directory, no_ext_file)
        try:
            with open(no_ext_path, 'r', encoding='utf-8', errors='ignore') as f:
                no_ext_content = f.read()
            
            # Find cookie keywords in baseline HTML
            found_keywords = []
            for keyword in cookie_keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', no_ext_content, re.IGNORECASE):
                    found_keywords.append(keyword)
            
            if found_keywords:
                if verbose:
                    tqdm.write(f"Cookie keywords found in baseline HTML: {', '.join(found_keywords)}")
                json_results["html_check"][f"visit{visit_num}"]["keywords"] = found_keywords
            else:
                if verbose:
                    tqdm.write("No cookie keywords found in baseline HTML")
        except Exception as e:
            if verbose:
                tqdm.write(f"Error processing {no_ext_file}: {e}")
            continue
        
        # For each extension file, check if these keywords are missing
        for ext_file in ext_files:
            if verbose:
                tqdm.write(f"Analyzing: {ext_file}")
            ext_path = os.path.join(directory, ext_file)
            try:
                with open(ext_path, 'r', encoding='utf-8', errors='ignore') as f:
                    ext_content = f.read()
                
                # If no keywords were found in baseline, we can't determine if banner was removed
                if not found_keywords:
                    if verbose:
                        tqdm.write("No baseline keywords to compare against - can't determine if banner was removed")
                    json_results["html_check"][f"visit{visit_num}"]["extensions"][ext_file] = {
                        "html": [],
                        "removal_indicated": False
                    }
                    continue
                
                # Check if keywords from baseline are missing
                missing_keywords = []
                matched_keywords = []
                for keyword in found_keywords:
                    if re.search(r'\b' + re.escape(keyword) + r'\b', ext_content, re.IGNORECASE):
                        matched_keywords.append(keyword)
                    else:
                        missing_keywords.append(keyword)
                
                json_results["html_check"][f"visit{visit_num}"]["extensions"][ext_file] = {
                    "html": matched_keywords,
                    "removal_indicated": len(missing_keywords) > 0
                }
                
                if missing_keywords:
                    if verbose:
                        tqdm.write(f"Keywords missing in extension HTML: {', '.join(missing_keywords)}")
                        tqdm.write("This indicates the cookie banner was likely handled by the extension")
                else:
                    if verbose:
                        tqdm.write("No keywords are missing - banner may still be present")
            except Exception as e:
                print(f"Error processing {ext_file}: {e}")
                # Mark as error in the results
                json_results["html_check"][f"visit{visit_num}"]["extensions"][ext_file] = {
                    "html": [],
                    "removal_indicated": False,
                    "error": str(e)
                }
    
    return json_results

if __name__ == "__main__":
    analyze_cookie_consent_text()
