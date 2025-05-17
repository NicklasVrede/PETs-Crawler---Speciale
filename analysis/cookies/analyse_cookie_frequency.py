import os
import json
from collections import defaultdict
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

def load_cookies(json_dir: str, domains_per_profile: int = 10) -> Dict[str, Dict[str, List[dict]]]:
    """
    Loads all cookies from JSON files.
    Args:
        json_dir: Directory containing profile subdirectories with JSON files
        domains_per_profile: If > 0, limit number of domains processed per profile
    Returns:
        Dictionary mapping domains to profiles to lists of cookies
    """
    domain_profile_cookies = defaultdict(lambda: defaultdict(list))
    profiles = [d for d in os.listdir(json_dir) if os.path.isdir(os.path.join(json_dir, d))]
    print(f"Looking for profiles in: {json_dir}")
    print(f"Found {len(profiles)} profiles: {', '.join(profiles)}\n")

    for profile_name in profiles:
        profile_path = os.path.join(json_dir, profile_name)
        print(f"Processing profile {profile_name} - found {len(os.listdir(profile_path))} domains")
        
        domain_files = [f for f in os.listdir(profile_path) if f.endswith(".json")]
        domain_files.sort()
        
        # Limit the number of domains processed per profile
        if domains_per_profile == None:
            files_to_process = domain_files
        else:
            files_to_process = domain_files[:domains_per_profile]

        for domain_file in tqdm(files_to_process, desc=f"Processing {profile_name}", unit="file"):
            file_path = os.path.join(profile_path, domain_file)
            domain_name = domain_file.replace(".json", "")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if data is None or not a dictionary
                if not isinstance(data, dict):
                    continue

                cookies_data = data.get('cookies')
                if not isinstance(cookies_data, dict):
                    continue

                # Get cookies from the "1" key if it exists, otherwise try "0"
                cookies = cookies_data.get("1", []) or cookies_data.get("0", [])
                
                if not isinstance(cookies, list):
                    continue

                for cookie in cookies:
                    if isinstance(cookie, dict):
                        domain_profile_cookies[domain_name][profile_name].append(cookie)

            except json.JSONDecodeError as e:
                print(f"Error processing {file_path}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred with {file_path}: {e}")
                
        print("") # Newline after each profile's progress bar

    return domain_profile_cookies

def analyze_cookie_frequency_by_profile(domain_profile_cookies: Dict[str, Dict[str, List[Dict[str, Any]]]], top_n: int = 12):
    """
    Analyze frequency of cookies across profiles and create separate bar charts for each profile.
    Args:
        domain_profile_cookies: Dictionary mapping domains to profiles to lists of cookies
        top_n: Number of top cookies to show individually
    """
    # Initialize counters for each profile
    cookie_counts_by_profile = defaultdict(lambda: defaultdict(int))
    
    # Count cookies for each profile
    for domain, profiles in domain_profile_cookies.items():
        for profile_name, cookies_list in profiles.items():
            for cookie in cookies_list:
                cookie_name = cookie.get('name', 'unknown')
                cookie_counts_by_profile[profile_name][cookie_name] += 1
    
    # Find the maximum count across all profiles for y-axis scaling
    max_count = 0
    for profile_counts in cookie_counts_by_profile.values():
        profile_max = max(profile_counts.values()) if profile_counts else 0
        max_count = max(max_count, profile_max)
    
    # Create output directory
    output_dir = 'analysis/cookies/frequency_analysis'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create separate plot for each profile
    for profile_name, cookie_counts in cookie_counts_by_profile.items():
        # Sort cookies by frequency
        sorted_cookies = sorted(cookie_counts.items(), key=lambda x: x[1], reverse=True)
        top_cookies = sorted_cookies[:top_n]
        
        # Create the plot
        plt.figure(figsize=(15, 8))
        
        # Extract cookie names and counts
        cookie_names = [cookie[0] for cookie in top_cookies]
        counts = [cookie[1] for cookie in top_cookies]
        
        # Create bar chart with common y-axis scale
        plt.bar(range(len(counts)), counts)
        plt.xticks(range(len(cookie_names)), cookie_names, rotation=45, ha='right')
        plt.ylim(0, max_count * 1.1)  # Add 10% padding to the top
        
        plt.xlabel('Cookie Name')
        plt.ylabel('Presence on origins')
        plt.title(f'Top {top_n} Most Common Cookies - Profile: {profile_name}')
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(output_dir, f'cookie_frequency_{profile_name}.png')
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()
        
        # Print statistics
        print(f"\nProfile: {profile_name}")
        total_cookies = sum(cookie_counts.values())
        print(f"Total cookies: {total_cookies}")
        print("\nTop cookies:")
        for cookie_name, count in top_cookies:
            percentage = (count / total_cookies) * 100
            print(f"  {cookie_name}: {count} ({percentage:.1f}%)")

def plot_cookie_frequencies(cookie_frequencies: Dict[str, Dict[str, int]], output_dir: str):
    """
    Create separate bar plots for each cookie name showing its frequency across profiles.
    Excludes 'Others' categories for clearer visualization.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all unique cookie names and profiles
    all_cookie_names = set()
    all_profiles = set()
    for profile_data in cookie_frequencies.values():
        all_cookie_names.update(profile_data.keys())
        all_profiles.add(profile)
    
    # Filter out "Others" categories
    cookie_names = [name for name in all_cookie_names if "Others" not in name]
    
    # For each cookie name
    for cookie_name in cookie_names:
        # Get counts for each profile
        profile_counts = []
        profile_names = []
        
        for profile in sorted(all_profiles):
            if profile in cookie_frequencies and cookie_name in cookie_frequencies[profile]:
                profile_counts.append(cookie_frequencies[profile][cookie_name])
                profile_names.append(profile)
        
        if not profile_counts:  # Skip if no data for this cookie
            continue
            
        # Create the plot
        plt.figure(figsize=(15, 8))
        plt.bar(range(len(profile_counts)), profile_counts)
        plt.xticks(range(len(profile_names)), profile_names, rotation=45, ha='right')
        plt.ylabel('Number of origins')
        plt.title(f'Number of origins setting "{cookie_name}" cookie by profile')
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Save the plot
        safe_name = "".join(c if c.isalnum() else "_" for c in cookie_name)
        output_path = os.path.join(output_dir, f'cookie_frequency_{safe_name}.png')
        plt.savefig(output_path)
        plt.close()
        
        print(f"Created plot for cookie '{cookie_name}' at {output_path}")

def main():
    json_dir = "data/crawler_data"
    
    print("Loading cookies...")
    domain_profile_cookies = load_cookies(json_dir, domains_per_profile=None)  # Limit to 10 domains
    
    if not domain_profile_cookies:
        print("No cookies found! Please check the data directory path.")
        return
    
    print("\nAnalyzing cookie frequencies...")
    analyze_cookie_frequency_by_profile(domain_profile_cookies)
    
    print("\nDone! Check the analysis files in analysis/cookies/frequency_analysis/")

if __name__ == "__main__":
    main()