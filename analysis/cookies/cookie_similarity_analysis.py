import os
import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from tqdm import tqdm

def load_cookies_from_json(json_dir, profile):
    """Load cookies from JSON files for a specific profile."""
    cookies_by_domain = defaultdict(list)
    
    # Get path to the profile directory
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        return cookies_by_domain

    # Find all JSON files
    json_files = []
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
                
    print(f"Found {len(json_files)} JSON files in {target_dir}")

    # Process each JSON file
    for json_file in tqdm(json_files, desc=f"Loading cookies for {profile}"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                domain = data.get('domain', os.path.basename(json_file)[:-5])  # Remove .json
                
                # Get cookies from visit "1"
                if 'cookies' in data and '1' in data['cookies']:
                    for cookie in data['cookies']['1']:
                        if 'classification' in cookie:
                            cookies_by_domain[domain].append({
                                'name': cookie.get('name'),
                                'domain': cookie.get('domain'),
                                'path': cookie.get('path'),
                                'category': cookie['classification'].get('category')
                            })
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            
    return cookies_by_domain

def calculate_cookie_similarity(cookies1, cookies2):
    """Calculate similarity between two sets of cookies."""
    set1 = {(c['name'], c['domain'], c['path']) for c in cookies1}
    set2 = {(c['name'], c['domain'], c['path']) for c in cookies2}
    
    if not set1 and not set2:
        return 1.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0

def analyze_cookie_similarity():
    # Base directory for crawler data
    json_dir = "data/Varies runs/crawler_data_trial02"
    
    # Profiles to analyze
    profiles = {
        'Opt-in': 'consent_o_matic_opt_in',
        'Opt-out': 'accept_all_cookies',
        'No extensions': 'no_extensions'
    }
    
    # Categories to analyze
    categories = ['Necessary', 'Functional', 'Advertisement', 'Analytics', 'Performance', 'Other']
    
    # Load baseline data
    print("Loading baseline data...")
    baseline_cookies = load_cookies_from_json(json_dir, "no_extensions")
    
    # Calculate similarities for each profile
    similarities = defaultdict(lambda: defaultdict(list))
    
    for profile_name, profile_dir in profiles.items():
        print(f"\nProcessing {profile_name}...")
        profile_cookies = load_cookies_from_json(json_dir, profile_dir)
        
        # For each domain that exists in both baseline and profile
        for domain in tqdm(set(baseline_cookies.keys()) & set(profile_cookies.keys())):
            # For each category
            for category in categories:
                # Filter cookies by category
                baseline_category_cookies = [
                    c for c in baseline_cookies[domain]
                    if c['category'] == category
                ]
                profile_category_cookies = [
                    c for c in profile_cookies[domain]
                    if c['category'] == category
                ]
                
                # Calculate similarity if we have cookies in either set
                if baseline_category_cookies or profile_category_cookies:
                    similarity = calculate_cookie_similarity(
                        baseline_category_cookies,
                        profile_category_cookies
                    )
                    similarities[profile_name][category].append(similarity)
    
    # Plotting
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(categories))
    width = 0.15  # Make bars narrower
    
    # Plot bars for each profile - adjust positions to group by category
    offsets = [-width, 0, width]  # Centers the group of 3 bars
    for i, (profile_name, color) in enumerate(zip(profiles.keys(), ['#333333', '#666666', '#999999'])):
        means = [np.mean(similarities[profile_name][cat]) if similarities[profile_name][cat] else 0 
                for cat in categories]
        errors = [np.std(similarities[profile_name][cat]) if len(similarities[profile_name][cat]) > 1 else 0 
                for cat in categories]
        
        ax.bar(x + offsets[i], means, width, label=profile_name, color=color, yerr=errors)
    
    # Customize the plot
    ax.set_ylabel('Similarity of the cookies')
    ax.set_title('Cookie type')
    ax.set_xticks(x)  # Center the category labels between the bar groups
    ax.set_xticklabels(categories, rotation=45)
    ax.legend(loc='upper right')
    ax.set_ylim(0, 1.0)
    
    # Add grid lines
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.savefig('cookie_similarity_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    analyze_cookie_similarity() 