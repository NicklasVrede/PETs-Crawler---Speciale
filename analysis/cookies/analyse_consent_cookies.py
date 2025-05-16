import os
import json
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any
import matplotlib.pyplot as plt
from tqdm import tqdm
import pandas as pd
import base64
import urllib.parse
import ast
import re

# Placeholder for known CMP cookie names or patterns
KNOWN_CMP_COOKIE_NAMES = [
    # "OptanonConsent",      # OneTrust
    "CookieConsent",       # Cookiebot / Usercentrics / Others using this common name
    # "eupubconsent-v2",     # IAB TCF v2
    # "euconsent-v2",        # IAB TCF v2 (alternative)
    # "_cmpRepromptHash",    # Sourcepoint
    # "usprivacy",           # IAB CCPA
    # "CONSENT",             # Google
    # "NID",                 # Google (often related, though broader)
    # "SAPISID",             # Google
    # "SID",                 # Google
    # "SOCS",                # Google
    # "ln_or",               # LiveRamp
    # "cmapi",               # Didomi
    # "didomi_token",        # Didomi
    # " बोरल्याण्ड ",         # CookieYes (sometimes seen with non-standard characters if issues)
    # "cky-consent",         # CookieYes
    # "cookieyes-consent",   # CookieYes
    # # Add more known CMP cookie names or patterns here
]

def parse_value_for_consent_options(value_str: str) -> Dict[str, Any]:
    """
    Tries to parse a cookie value to find structured data that might represent consent options.
    Supports JS-object-literal-like strings, JSON, and URL-encoded query strings.
    Returns a dictionary of parsed key-value pairs if successful, otherwise an empty dictionary.
    """
    if not isinstance(value_str, str):
        return {}

    # Attempt 1: Try to parse as JS-object-literal-like string by transforming it
    # This is common for 'CookieConsent' type cookies.
    # Example: {stamp:'foo',necessary:true,preferences:false}
    if value_str.startswith('{') and value_str.endswith('}'):
        transformed_str = value_str[1:-1]  # Remove outer braces

        # Replace JS true/false/null with Python True/False/None for ast.literal_eval
        transformed_str = re.sub(r'\btrue\b', 'True', transformed_str, flags=re.IGNORECASE)
        transformed_str = re.sub(r'\bfalse\b', 'False', transformed_str, flags=re.IGNORECASE)
        transformed_str = re.sub(r'\bnull\b', 'None', transformed_str, flags=re.IGNORECASE)

        # Add double quotes around unquoted keys to make it valid for ast.literal_eval
        # This regex targets keys like `key:` and turns them into `"key":`
        # It handles keys at the start of the string or preceded by a comma/brace and whitespace.
        # Regex for keys: an identifier [a-zA-Z_][a-zA-Z0-9_]*
        
        # Quote keys preceded by '{' or ',' or whitespace
        quoted_keys_str = re.sub(r"([{\s,])([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', transformed_str)
        # Quote key if it's at the very beginning of the (inner) string
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:", quoted_keys_str):
            quoted_keys_str = re.sub(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'"\1":', quoted_keys_str)
        
        final_eval_str = "{" + quoted_keys_str + "}"

        try:
            data = ast.literal_eval(final_eval_str)
            if isinstance(data, dict):
                return data
        except (SyntaxError, ValueError, TypeError):
            # If ast.literal_eval fails, proceed to other methods
            pass

    # Attempt 2: Try direct JSON parsing (if keys were already double quoted)
    try:
        data = json.loads(value_str)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt 3: Try parsing as URL-encoded query string
    try:
        # Only attempt if it looks like a query string
        if isinstance(value_str, str) and ('=' in value_str or '&' in value_str):
            query_params = urllib.parse.parse_qs(value_str, keep_blank_values=True)
            simplified_params = {}
            if query_params: # Ensure parse_qs actually found parameters
                for k, v_list in query_params.items():
                    # Take the first value if a list exists, otherwise empty string for blank values
                    simplified_params[k] = v_list[0] if v_list else ""
                if simplified_params: # Make sure we have something to return
                    return simplified_params
    except Exception: # Broad exception for any parsing issues with urllib
        pass

    return {}

def find_all_matching_substrings(strings: List[str]) -> List[Tuple[str, List[int]]]:
    """Find common substrings that appear in multiple strings.
    Returns list of tuples (substring, [indices where it appears])."""
    if not strings or len(strings) <= 1:
        return []
    
    results = []
    for i, s1 in enumerate(strings):
        for j, s2 in enumerate(strings[i+1:], i+1):
            common = find_common_substring(s1, s2)
            if common and len(common) > 3:  # Only meaningful substrings (>3 chars)
                indices = [idx for idx, s in enumerate(strings) if common in s]
                results.append((common, indices))
    
    return results

def find_common_substring(s1: str, s2: str) -> str:
    """Find the longest common substring between two strings."""
    if not s1 or not s2:
        return ""
        
    s1, s2 = s1.lower(), s2.lower()
    m = [[0] * (len(s2) + 1) for _ in range(len(s1) + 1)]
    longest, end_pos = 0, 0
    
    for i in range(1, len(s1) + 1):
        for j in range(1, len(s2) + 1):
            if s1[i-1] == s2[j-1]:
                m[i][j] = m[i-1][j-1] + 1
                if m[i][j] > longest:
                    longest = m[i][j]
                    end_pos = i
    
    return s1[end_pos - longest:end_pos]

def is_encrypted_session(value: str) -> bool:
    """Check if value appears to be an encrypted session cookie."""
    # Check for the common encrypted session pattern: data--signature
    if '--' in value and (value.endswith('=') or value.endswith('==')):
        return True
    return False

def is_readable_value(value: str) -> bool:
    """Check if the value appears to be human-readable."""
    try:
        # URL decode first
        decoded = urllib.parse.unquote(value)
        
        # Check for JSON-like structure
        if decoded.startswith('{') and decoded.endswith('}'):
            json.loads(decoded)
            return True
            
        # Check for simple true/false values
        if decoded.lower() in ['true', 'false', '0', '1']:
            return True
            
        # Check for common consent patterns (pipe-separated values)
        if '|' in decoded and any(x in decoded.lower() for x in ['consent', 'preference']):
            return True
            
        return False
    except:
        return False

def is_cmp_cookie(cookie: dict) -> bool:
    """Check if cookie is likely from a known CMP based on its name (exact match)."""
    if not cookie or 'name' not in cookie:
        return False
    
    cookie_name = cookie.get('name', '') # Ensure cookie_name is a string
    if not isinstance(cookie_name, str): # Handle cases where name might not be a string
        return False
    
    cookie_name_lower = cookie_name.lower()
    
    for cmp_indicator in KNOWN_CMP_COOKIE_NAMES:
        # Perform an exact match (case-insensitive)
        if cmp_indicator.lower() == cookie_name_lower:
            return True
    return False

def load_cmp_cookies(json_dir: str, domains_per_profile: int = 10) -> Dict[str, Dict[str, List[dict]]]:
    """
    Loads cookies from JSON files, focusing on known CMP cookies.
    Handles JSON decoding errors and missing 'cookies' key.
    """
    domain_profile_cmp_cookies = defaultdict(lambda: defaultdict(list))
    profiles = [d for d in os.listdir(json_dir) if os.path.isdir(os.path.join(json_dir, d))]
    print(f"Looking for profiles in: {json_dir}")
    print(f"Found {len(profiles)} profiles: {', '.join(profiles)}\n")

    for profile_name in profiles:
        profile_path = os.path.join(json_dir, profile_name)
        print(f"Processing profile {profile_name} - found {len(os.listdir(profile_path))} domains")
        
        domain_files = [f for f in os.listdir(profile_path) if f.endswith(".json")]
        
        # Sort domain files for consistent processing order (optional, but good for reproducibility)
        domain_files.sort()
        
        # Limit the number of domains processed per profile if domains_per_profile is set
        files_to_process = domain_files[:domains_per_profile] if domains_per_profile > 0 else domain_files

        for domain_file in tqdm(files_to_process, desc=f"Processing {profile_name}", unit="file"):
            file_path = os.path.join(profile_path, domain_file)
            domain_name = domain_file.replace(".json", "")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if data is None (e.g., if JSON file was just "null") or not a dictionary
                if not isinstance(data, dict):
                    # print(f"Warning: Data in {file_path} is not a dictionary, skipping.")
                    continue

                cookies = data.get('cookies') # Use .get() for safer access

                # Check if 'cookies' key exists and is a list
                if cookies is None:
                    # print(f"Warning: No 'cookies' key found in {file_path}, skipping.")
                    continue
                if not isinstance(cookies, list):
                    # print(f"Warning: 'cookies' in {file_path} is not a list, skipping.")
                    continue

                found_cmp_for_domain_profile = False
                for cookie in cookies:
                    if isinstance(cookie, dict) and is_cmp_cookie(cookie):
                        domain_profile_cmp_cookies[domain_name][profile_name].append(cookie)
                        found_cmp_for_domain_profile = True
                
                if found_cmp_for_domain_profile:
                    # This print can be verbose if many domains have CMP cookies.
                    # Consider removing or adjusting if output is too noisy.
                    # print(f"Found {len(domain_profile_cmp_cookies[domain_name][profile_name])} CMP cookies in {domain_name} for profile {profile_name}")
                    pass

            except json.JSONDecodeError as e:
                print(f"Error processing {file_path}: {e}")
            except Exception as e: # Catch other potential errors during file processing
                print(f"An unexpected error occurred with {file_path}: {e}")
        print("") # Newline after each profile's progress bar

    return domain_profile_cmp_cookies

def try_decode_value(value: str) -> str:
    """Attempt to decode a cookie value that might be encoded."""
    try:
        # First try URL decoding
        url_decoded = urllib.parse.unquote(value)
        
        # Then try base64 decoding
        if '==' in url_decoded:  # Base64 padding check
            try:
                decoded = base64.b64decode(url_decoded).decode('utf-8')
                return decoded
            except:
                pass
        return url_decoded
    except:
        return value

def analyze_json_like_value(value: str) -> Dict[str, Any]:
    """Extract key-value pairs from a JSON-like string."""
    try:
        # Clean up the string to make it valid JSON
        cleaned = value.replace('%27', "'").replace('%2C', ',')
        if cleaned.startswith('{') and cleaned.endswith('}'):
            data = json.loads(cleaned.replace("'", '"'))
            return {k: v for k, v in data.items() 
                   if isinstance(v, (bool, str, int)) and 
                   (str(v).lower() in ['true', 'false'] or k in ['method', 'region'])}
    except:
        return {}

def analyze_consent_patterns(cookies: List[dict]) -> None:
    """Analyze consent patterns across profiles."""
    patterns_by_profile = defaultdict(dict)
    
    for cookie in cookies:
        value = urllib.parse.unquote(cookie['value'])
        profile = cookie['profile']
        
        # Try to parse as JSON-like structure
        consent_values = analyze_json_like_value(value)
        if consent_values:
            # Store the consent pattern for this profile
            patterns_by_profile[profile].update(consent_values)
    
    # Group profiles by their consent patterns
    pattern_groups = defaultdict(list)
    for profile, patterns in patterns_by_profile.items():
        key = tuple(sorted((k, str(v)) for k, v in patterns.items()))
        pattern_groups[key].append(profile)
    
    # Output the patterns
    print("\nConsent Patterns:")
    print("================")
    for pattern, profiles in pattern_groups.items():
        print("\nPattern:")
        for k, v in pattern:
            print(f"  {k}: {v}")
        print("\nUsed by profiles:")
        for profile in sorted(profiles):
            print(f"  - {profile}")
        print("-" * 50)

def analyze_cmp_cookies(domain_profile_cmp_cookies: Dict[str, Dict[str, List[Dict[str, Any]]]], output_dir="analysis/cookies/cmp_analysis"):
    """Analyze CMP cookies and write details to a file."""
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, "cmp_cookies_details.txt")

    with open(output_file_path, "w", encoding="utf-8") as f:
        for domain, profiles in domain_profile_cmp_cookies.items():
            f.write(f"Domain: {domain}\n")
            f.write(f"========================\n")
            
            domain_parsed_cookie_consent_values = {} # For grouping CookieConsent values

            for profile_name, cmp_cookies_list in profiles.items():
                f.write(f"\n  Profile: {profile_name}\n")
                if not cmp_cookies_list:
                    f.write(f"  No CMP cookies found for this profile/domain based on current KNOWN_CMP_COOKIE_NAMES.\n")
                    f.write("  ----------------------------------------\n")
                    continue

                f.write(f"  Found {len(cmp_cookies_list)} CMP cookie(s) for this profile/domain.\n")
                
                for cmp_cookie in cmp_cookies_list:
                    f.write(f"\n    Cookie Name: {cmp_cookie.get('name', 'N/A')}\n")
                    
                    value_to_write = cmp_cookie.get('value', '')
                    decoded_value_str = ""

                    if isinstance(value_to_write, str):
                        try:
                            decoded_value = urllib.parse.unquote(value_to_write)
                            f.write(f"    Value (decoded): {decoded_value}\n")
                            decoded_value_str = decoded_value
                        except Exception:
                            f.write(f"    Value (raw): {value_to_write}\n")
                            decoded_value_str = value_to_write
                    else:
                         f.write(f"    Value: {value_to_write}\n")
                         decoded_value_str = str(value_to_write)

                    if decoded_value_str:
                        parsed_options = parse_value_for_consent_options(decoded_value_str)
                        if parsed_options:
                            # Filter for boolean values only for display
                            boolean_options_display = {
                                k: v for k, v in parsed_options.items() if isinstance(v, bool)
                            }
                            if boolean_options_display:
                                f.write(f"    Parsed Value Options (Booleans Only):\n")
                                for pk, pv in sorted(boolean_options_display.items()):
                                    f.write(f"      - {str(pk)}: {str(pv)}\n")
                            
                            # Store for grouping if it's a CookieConsent cookie, using only boolean values
                            if cmp_cookie.get('name', '').lower() == 'cookieconsent':
                                boolean_options_grouping = {
                                    k: v for k, v in parsed_options.items() if isinstance(v, bool)
                                }
                                # Only add to grouping if there are boolean options to group by
                                if boolean_options_grouping:
                                    domain_parsed_cookie_consent_values[profile_name] = frozenset(boolean_options_grouping.items())
                        
                    f.write(f"    Cookie Domain: {cmp_cookie.get('domain', 'N/A')}\n")
                    f.write(f"    Path: {cmp_cookie.get('path', 'N/A')}\n")
                    f.write(f"    Category (from source): {cmp_cookie.get('category', 'N/A')}\n")
                    f.write(f"    Description (from source): {cmp_cookie.get('description', 'N/A')}\n")
                    f.write(f"    Script (from source): {cmp_cookie.get('script', 'N/A')}\n")
                f.write("\n  " + "-" * 40 + "\n")

            # After processing all profiles for a domain, print grouping for CookieConsent
            if domain_parsed_cookie_consent_values:
                f.write("\n  ----------------------------------------\n")
                f.write("  Profile Grouping for 'CookieConsent' (Boolean Values Only):\n")
                
                value_to_profiles = defaultdict(list)
                for profile, parsed_val_fset in domain_parsed_cookie_consent_values.items():
                    value_to_profiles[parsed_val_fset].append(profile)
                
                group_num = 1
                for parsed_val_fset, profile_list in value_to_profiles.items():
                    # Check if the frozenset is not empty before trying to create a hash or print
                    if not parsed_val_fset: # Should not happen if we only add non-empty boolean_options_grouping
                        continue

                    f.write(f"    Group {group_num} (Value hash: {hash(parsed_val_fset)}):\n")
                    f.write(f"      Profiles: {', '.join(sorted(profile_list))}\n")
                    f.write(f"      Parsed Boolean Values:\n")
                    temp_dict = dict(parsed_val_fset) # Will only contain boolean key-value pairs
                    for pk, pv in sorted(temp_dict.items()):
                        f.write(f"        - {str(pk)}: {str(pv)}\n")
                    group_num += 1
            
            f.write("\n==================================================\n\n")

def main():
    json_dir = "data/crawler_data"
    
    print("Loading CMP cookies...")
    domain_profile_cmp_cookies = load_cmp_cookies(json_dir, domains_per_profile=50) # Use a small number for testing
    
    if not domain_profile_cmp_cookies:
        print("No CMP cookies found! Please check the data directory path or CMP indicators.")
        return
    
    print("\nAnalyzing CMP cookies...")
    analyze_cmp_cookies(domain_profile_cmp_cookies)

    # Optional: Analyze patterns in the values of these CMP cookies
    all_cmp_cookies_for_pattern_analysis = []
    for domain, profile_data in domain_profile_cmp_cookies.items():
        for profile, cookies_list in profile_data.items():
            for cookie_dict in cookies_list:
                cookie_with_profile = cookie_dict.copy()
                # Ensure 'profile' key is added for analyze_consent_patterns
                cookie_with_profile['profile'] = profile
                all_cmp_cookies_for_pattern_analysis.append(cookie_with_profile)
    
    if all_cmp_cookies_for_pattern_analysis:
        print("\nAnalyzing CMP cookie value patterns (output to console)...")
        analyze_consent_patterns(all_cmp_cookies_for_pattern_analysis)
    else:
        print("\nNo CMP cookies available for pattern analysis.")
        
    print("\nDone! Check the analysis files in analysis/cookies/cmp_analysis/")

if __name__ == "__main__":
    main()
