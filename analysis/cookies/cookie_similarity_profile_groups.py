import os
import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from tqdm import tqdm
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

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
    # Base directory for crawler data
    json_dir = "data/Varies runs/crawler_data_trial02"
    
    # Get list of actually existing profiles
    existing_profiles = {}
    for profile_id, display_name in DISPLAY_NAMES.items():
        profile_path = os.path.join(json_dir, profile_id)
        if os.path.exists(profile_path):
            # Check if directory contains JSON files
            json_files = [f for f in os.listdir(profile_path) if f.endswith('.json')]
            if json_files:
                existing_profiles[profile_id] = display_name
                print(f"Found profile: {display_name} ({len(json_files)} JSON files)")
            else:
                print(f"Skipping {display_name} - no JSON files found")
        else:
            print(f"Skipping {display_name} - directory not found")
    
    print(f"\nFound {len(existing_profiles)} valid profiles")
    
    # Load cookies for existing profiles
    profile_cookies = {}
    for profile_id, display_name in existing_profiles.items():
        print(f"\nLoading cookies for {display_name}...")
        profile_cookies[profile_id] = load_cookies_from_json(json_dir, profile_id)
    
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
    
    # Add x-axis labels
    plt.xticks(range(len(ordered_profiles)), 
               [DISPLAY_NAMES[p] for p in ordered_profiles], 
               rotation=45, ha='right')
    
    # Add group separators and labels
    current_pos = 0
    group_positions = []  # Store middle position of each group
    
    # First pass: add vertical lines and collect group positions
    for group in ["Baseline Profile", "Traditional PETs", "Cookie Extensions", "Other"]:
        group_size = sum(1 for p in PROFILE_GROUPS[group] if p in existing_profiles)
        if current_pos > 0 and group_size > 0:
            plt.axvline(x=current_pos - 0.5, color='black', linewidth=2)
        
        # Store middle position of group for label placement
        if group_size > 0:
            group_positions.append((current_pos + group_size/2, group))
        current_pos += group_size
    
    # Add y-axis labels with group labels
    y_labels = [DISPLAY_NAMES[p] for p in ordered_profiles]
    plt.yticks(range(len(ordered_profiles)), y_labels)
    
    # Add group labels on the left
    ax = plt.gca()
    ax.set_ylabel('')  # Remove default y-label
    
    # Add group labels with increased spacing
    label_padding = 1.3  # Adjust this value to move labels further left
    for pos, group in group_positions:
        plt.text(-len(max(y_labels, key=len)) * label_padding, pos, 
                group, 
                rotation=90, 
                va='center', 
                ha='center',
                fontweight='bold')
    
    # Add text annotations
    for i in range(len(ordered_profiles)):
        for j in range(len(ordered_profiles)):
            color = 'black' if similarity_values[i, j] < 0.7 else 'white'
            plt.text(j, i, f'{similarity_values[i, j]:.2f}',
                    ha='center', va='center', color=color)
    
    plt.title('Profile Similarity Heatmap', pad=20)
    plt.tight_layout()
    
    # Adjust layout to make room for group labels
    plt.subplots_adjust(left=0.2)  # Adjust this value if needed
    
    plt.savefig('profile_similarity_heatmap.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    analyze_profile_similarities() 