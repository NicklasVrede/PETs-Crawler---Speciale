import os
import re
import json
from collections import defaultdict
from tqdm import tqdm

def analyze_cookie_consent_text(directory_path="data/banner_data/html/active.com", verbose=False):
    """Analyze HTML files for cookie consent text and update JSON results
    
    Args:
        directory_path: Path to directory with HTML files
        json_file_path: Path to save or update JSON results
        save_to_json: Whether to save results to JSON file
        
    Returns:
        dict: Analysis results with keywords found and extension results
    """
    
    # Get all HTML files in the directory
    all_files = [f for f in os.listdir(directory_path) if f.endswith('.html')]
    
    # Separate no_extension files from others using case-insensitive matching
    no_extension_files = [f for f in all_files if 'no_extension'.lower() in f.lower()]
    extension_files = [f for f in all_files if 'no_extension'.lower() not in f.lower()]
    
    if verbose:
        tqdm.write(f"Found {len(no_extension_files)} no_extension HTML files and {len(extension_files)} extension HTML files")
    
    # Load existing JSON or create new structure
    json_results = {}
    
    # Group files by visit number for comparison
    visit_groups = defaultdict(lambda: {'no_extension': None, 'extensions': []})
    
    for file in no_extension_files:
        visit_match = re.search(r'visit(\d+)_no_extension', file, re.IGNORECASE)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['no_extension'] = file
    
    for file in extension_files:
        visit_match = re.search(r'visit(\d+)_', file, re.IGNORECASE)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['extensions'].append(file)
    
    # Define consent phrases to look for
    consent_phrases = [
        "accept all", "accept cookies", "i accept", 
        "deny all", "reject all", "decline", 
        "manage cookies", "cookie settings", "cookie preferences",
        "agree", "consent", "i understand",
        "privacy policy", "cookie policy"
    ]
    
    # Compare each no_extension file with its corresponding extension files
    for visit_num, files in visit_groups.items():
        no_ext_file = files['no_extension']
        ext_files = files['extensions']
        
        if not no_ext_file:
            continue
            
        if verbose:
            print(f"--- Analyzing Visit {visit_num} HTML ---")
            print(f"Baseline: {no_ext_file}")
        
        # Initialize or update the visit entries in JSON
        visit_id = f"visit{visit_num}"
        
        if "html_check" not in json_results:
            json_results["html_check"] = {}
            
        if visit_id not in json_results["html_check"]:
            json_results["html_check"][visit_id] = {
                "keywords": [],
                "no_extension": {"matches": []},
                "extensions": {}
            }
        
        # Load the no_extension HTML
        try:
            with open(os.path.join(directory_path, no_ext_file), 'r', encoding='utf-8', errors='ignore') as f:
                no_ext_html = f.read()
            
            # Find consent text in baseline file
            baseline_consent_phrases = []
            for phrase in consent_phrases:
                # Case-insensitive search in the HTML content
                pattern = re.compile(phrase, re.IGNORECASE)
                if pattern.search(no_ext_html):
                    baseline_consent_phrases.append(phrase)
            
            if baseline_consent_phrases:
                if verbose:
                    tqdm.write(f"Consent phrases found in baseline: {', '.join(baseline_consent_phrases)}")
                json_results["html_check"][visit_id]["keywords"] = baseline_consent_phrases
                json_results["html_check"][visit_id]["no_extension"]["matches"] = baseline_consent_phrases
            else:
                if verbose:
                    tqdm.write("No consent phrases found in baseline")
        except Exception as e:
            if verbose:
                tqdm.write(f"Error processing baseline file {no_ext_file}: {e}")
            continue
        
        # For each extension file, check if these phrases are missing
        for ext_file in ext_files:
            if verbose:
                tqdm.write(f"\nAnalyzing: {ext_file}")
            try:
                with open(os.path.join(directory_path, ext_file), 'r', encoding='utf-8', errors='ignore') as f:
                    ext_html = f.read()
                
                # Find which baseline phrases are missing in this extension file
                missing_phrases = []
                found_phrases = []
                for phrase in baseline_consent_phrases:
                    pattern = re.compile(phrase, re.IGNORECASE)
                    if pattern.search(ext_html):
                        found_phrases.append(phrase)
                    else:
                        missing_phrases.append(phrase)
                        
                # Initialize the extension entry
                json_results["html_check"][visit_id]["extensions"][ext_file] = {
                    "matches": found_phrases,
                    "missing": missing_phrases
                }
                
                if missing_phrases:
                    if verbose:
                        tqdm.write(f"Consent phrases missing in this file: {', '.join(missing_phrases)}")
                        tqdm.write("This indicates the cookie banner was likely handled by the extension")
                else:
                    if verbose:
                        tqdm.write("No consent phrases are missing - banner may still be present")
            except Exception as e:
                if verbose:
                    tqdm.write(f"Error processing {ext_file}: {e}")
                json_results["html_check"][visit_id]["extensions"][ext_file] = {
                    "matches": [],
                    "missing": [],
                    "error": str(e)
                }
        
    return json_results

if __name__ == "__main__":
    analyze_cookie_consent_text()
