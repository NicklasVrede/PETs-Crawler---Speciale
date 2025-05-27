import os
import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from tqdm import tqdm
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS
from analysis.third_party.third_party_domain_prevalence import get_successful_domains

def load_cookies_from_json(json_dir, profile, successful_domains):
    """Load cookies from JSON files for a specific profile."""
    cookies_by_domain = defaultdict(list)
    
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        return cookies_by_domain

    # Only process JSON files for successful domains
    json_files = []
    for domain in successful_domains:
        json_file = os.path.join(target_dir, f"{domain}.json")
        if os.path.exists(json_file):
            json_files.append(json_file)
    
    print(f"Found {len(json_files)} JSON files in {target_dir}")

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
    # Create sets of cookie identifiers (name + domain + path)
    set1 = {(c['name'], c['domain'], c['path']) for c in cookies1}
    set2 = {(c['name'], c['domain'], c['path']) for c in cookies2}
    
    # Calculate Jaccard similarity
    if not set1 and not set2:
        return 1.0  # Both sets empty = perfect similarity
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0

def analyze_profile_similarities():
    json_dir = "data/crawler_data"
    
    # Get list of actually existing profiles
    existing_profiles = {}
    for profile_id, display_name in DISPLAY_NAMES.items():
        profile_path = os.path.join(json_dir, profile_id)
        if os.path.exists(profile_path):
            existing_profiles[profile_id] = display_name
            print(f"Found profile: {display_name}")
        else:
            print(f"Skipping {display_name} - directory not found")
    
    print(f"\nFound {len(existing_profiles)} valid profiles")

    # Get domains that loaded successfully across all profiles
    successful_domains = get_successful_domains()
    print(f"\nFound {len(successful_domains)} domains that loaded successfully across all profiles")
    
    # Load cookies for existing profiles
    profile_cookies = {}
    for profile_id, display_name in existing_profiles.items():
        print(f"\nLoading cookies for {display_name}...")
        profile_cookies[profile_id] = load_cookies_from_json(json_dir, profile_id, successful_domains)
    
    # Calculate similarity matrix between all existing profiles
    similarity_matrix = defaultdict(dict)
    print("\nCalculating similarities between profiles...")
    
    for profile1 in existing_profiles:
        for profile2 in existing_profiles:
            if profile1 != profile2:  # Skip self-comparison
                total_similarity = 0
                domain_count = 0
                
                # Get common domains
                common_domains = set(profile_cookies[profile1].keys()) & set(profile_cookies[profile2].keys())
                
                for domain in tqdm(common_domains, 
                                 desc=f"Comparing {existing_profiles[profile1]} vs {existing_profiles[profile2]}"):
                    cookies1 = profile_cookies[profile1][domain]
                    cookies2 = profile_cookies[profile2][domain]
                    
                    if cookies1 and cookies2:  # Only compare if both have cookies
                        similarity = calculate_cookie_similarity(cookies1, cookies2)
                        total_similarity += similarity
                        domain_count += 1
                
                avg_similarity = total_similarity / domain_count if domain_count > 0 else 0
                similarity_matrix[profile1][profile2] = avg_similarity
    
    # Print results
    print("\nProfile Similarity Analysis:")
    print("=" * 80)
    for profile1 in existing_profiles:
        print(f"\n{existing_profiles[profile1]}:")
        similarities = [(p2, similarity_matrix[profile1][p2]) 
                       for p2 in existing_profiles if p2 != profile1]
        similarities.sort(key=lambda x: x[1], reverse=True)
        for other_profile, score in similarities:
            print(f"  Similarity to {existing_profiles[other_profile]}: {score:.3f}")
    
    # Use all profiles from PROFILE_GROUPS in their defined order, but filter for existing ones
    ordered_profiles = []
    for group in ["Baseline Profile", "Traditional PETs", "Cookie Extensions", "Other"]:
        ordered_profiles.extend([p for p in PROFILE_GROUPS[group] if p in existing_profiles])
    
    # Create a heatmap visualization
    plt.figure(figsize=(15, 12))
    
    # Create similarity matrix with ordered profiles
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
    
    # Add x and y-axis labels (profile names only)
    plt.xticks(range(len(ordered_profiles)), 
               [DISPLAY_NAMES[p] for p in ordered_profiles], 
               rotation=45, ha='right')
    plt.yticks(range(len(ordered_profiles)), 
               [DISPLAY_NAMES[p] for p in ordered_profiles])
    
    # Add group separators
    current_pos = 0
    for group in ["Baseline Profile", "Traditional PETs", "Cookie Extensions", "Other"]:
        group_size = sum(1 for p in PROFILE_GROUPS[group] if p in existing_profiles)
        if current_pos > 0 and group_size > 0:
            plt.axvline(x=current_pos - 0.5, color='black', linewidth=2)
            plt.axhline(y=current_pos - 0.5, color='black', linewidth=2)
        current_pos += group_size
    
    # Add text annotations
    for i in range(len(ordered_profiles)):
        for j in range(len(ordered_profiles)):
            color = 'black' if similarity_values[i, j] < 0.7 else 'white'
            plt.text(j, i, f'{similarity_values[i, j]:.2f}',
                    ha='center', va='center', color=color)
    
    plt.tight_layout()
    plt.savefig('profile_similarity_heatmap.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    analyze_profile_similarities() 