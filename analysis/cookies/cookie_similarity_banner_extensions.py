import os
import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from tqdm import tqdm
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

def load_cookies_from_json(json_dir, profile):
    """Load cookies from JSON files for a specific profile."""
    cookies_by_domain = defaultdict(list)
    
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        return cookies_by_domain

    json_files = []
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))

    for json_file in tqdm(json_files, desc=f"Loading cookies for {profile}"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                domain = data.get('domain', os.path.basename(json_file)[:-5])
                
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

def analyze_banner_extension_similarities():
    json_dir = "data/crawler_data"
    
    # Get cookie banner extensions and baseline profile
    banner_profiles = PROFILE_GROUPS['Cookie Extensions'] + ['no_extensions']
    
    # Get list of actually existing profiles
    existing_profiles = {}
    for profile_id in banner_profiles:
        if profile_id in DISPLAY_NAMES:
            profile_path = os.path.join(json_dir, profile_id)
            if os.path.exists(profile_path):
                json_files = [f for f in os.listdir(profile_path) if f.endswith('.json')]
                if json_files:
                    existing_profiles[profile_id] = DISPLAY_NAMES[profile_id]
                    print(f"Found profile: {DISPLAY_NAMES[profile_id]} ({len(json_files)} JSON files)")
    
    print(f"\nFound {len(existing_profiles)} valid profiles")
    
    # Load cookies for existing profiles
    profile_cookies = {}
    for profile_id in existing_profiles:
        print(f"\nLoading cookies for {existing_profiles[profile_id]}...")
        profile_cookies[profile_id] = load_cookies_from_json(json_dir, profile_id)
    
    # Calculate similarity matrix
    similarity_matrix = defaultdict(dict)
    print("\nCalculating similarities between profiles...")
    
    for profile1 in existing_profiles:
        for profile2 in existing_profiles:
            if profile1 != profile2:
                total_similarity = 0
                domain_count = 0
                
                common_domains = set(profile_cookies[profile1].keys()) & set(profile_cookies[profile2].keys())
                
                for domain in common_domains:
                    cookies1 = profile_cookies[profile1][domain]
                    cookies2 = profile_cookies[profile2][domain]
                    
                    if cookies1 and cookies2:
                        similarity = calculate_cookie_similarity(cookies1, cookies2)
                        total_similarity += similarity
                        domain_count += 1
                
                avg_similarity = total_similarity / domain_count if domain_count > 0 else 0
                similarity_matrix[profile1][profile2] = avg_similarity
    
    # Create ordered list of profiles (baseline first, then extensions)
    ordered_profiles = ['no_extensions'] + [p for p in banner_profiles if p != 'no_extensions' and p in existing_profiles]
    
    # Create heatmap visualization
    plt.figure(figsize=(10, 8))
    
    similarity_values = np.zeros((len(ordered_profiles), len(ordered_profiles)))
    for i, p1 in enumerate(ordered_profiles):
        for j, p2 in enumerate(ordered_profiles):
            if i != j:
                similarity_values[i][j] = similarity_matrix[p1][p2]
            else:
                similarity_values[i][j] = 1.0
    
    # Plot with YlOrRd colormap
    im = plt.imshow(similarity_values, cmap='YlOrRd')
    plt.colorbar(label='Similarity Score')
    
    # Add labels
    plt.xticks(range(len(ordered_profiles)), 
               [DISPLAY_NAMES[p] for p in ordered_profiles], 
               rotation=45, ha='right')
    plt.yticks(range(len(ordered_profiles)), 
               [DISPLAY_NAMES[p] for p in ordered_profiles])
    
    # Add text annotations
    for i in range(len(ordered_profiles)):
        for j in range(len(ordered_profiles)):
            color = 'black' if similarity_values[i, j] < 0.7 else 'white'
            plt.text(j, i, f'{similarity_values[i, j]:.2f}',
                    ha='center', va='center', color=color)
    
    plt.title('Cookie Extension Similarity Heatmap')
    plt.tight_layout()
    plt.savefig('analysis/graphs/cookie_extension_similarity_heatmap.png', 
                dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    analyze_banner_extension_similarities() 