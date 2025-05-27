import os
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
import sys
from matplotlib.patheffects import Stroke, Normal

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Create output directory if it doesn't exist
output_dir = os.path.join(project_root, 'analysis', 'graphs', 'cookie_similarities_successful_removals')
os.makedirs(output_dir, exist_ok=True)

def get_successful_domains_with_removals():
    """Get domains that loaded successfully AND had banners removed for consent management extensions."""
    # Read the CSV file
    df = pd.read_csv('data/csv/final_data2.csv')
    
    # Define consent management profiles that should have banner removal
    consent_profiles = [
        'consent_o_matic_opt_out',
        'consent_o_matic_opt_in',
        'super_agent_opt_out',
        'super_agent_opt_in'
    ]
    
    # Get successful domains for no_extensions (only check page_loaded)
    baseline_domains = set(df[
        (df['profile'] == 'no_extensions') & 
        (df['page_loaded'] == True)
    ]['domain'])
    
    # Get successful domains for consent management profiles (check both page_loaded and banner_removed)
    consent_domains = set(df[
        (df['profile'].isin(consent_profiles)) & 
        (df['page_loaded'] == True) &
        (df['banner_removed'] == True)
    ]['domain'])
    
    # Find domains that were successful across all profiles
    successful_domains = baseline_domains.intersection(consent_domains)
    
    print(f"Found {len(successful_domains)} domains that:")
    print(f"- Loaded successfully in baseline profile")
    print(f"- Loaded successfully AND had banners removed by consent management extensions")
    
    return list(successful_domains)

def load_cookies_from_json(json_dir, profile, successful_domains):
    """Load cookies from JSON files for a specific profile."""
    cookies_by_domain = defaultdict(list)
    
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        return cookies_by_domain

    json_files = []
    for domain in successful_domains:
        json_file = os.path.join(target_dir, f"{domain}.json")
        if os.path.exists(json_file):
            json_files.append(json_file)

    for json_file in tqdm(json_files, desc=f"Loading cookies for {profile}"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                domain = data.get('domain', os.path.basename(json_file)[:-5])
                
                if 'cookies' in data and '1' in data['cookies']:
                    for cookie in data['cookies']['1']:
                        if 'classification' in cookie:
                            category = cookie['classification'].get('category', 'Unknown')
                            cookies_by_domain[domain].append({
                                'name': cookie.get('name'),
                                'domain': cookie.get('domain'),
                                'path': cookie.get('path'),
                                'category': category
                            })
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            
    return cookies_by_domain

def calculate_cookie_similarity_by_category(cookies1, cookies2, category):
    """Calculate similarity between two sets of cookies for a specific category."""
    cookies1_category = [c for c in cookies1 if c['category'] == category]
    cookies2_category = [c for c in cookies2 if c['category'] == category]
    
    set1 = {(c['name'], c['domain'], c['path']) for c in cookies1_category}
    set2 = {(c['name'], c['domain'], c['path']) for c in cookies2_category}
    
    if not set1 and not set2:
        return 1.0  # Both sets empty means they're identical
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def analyze_banner_extension_similarities_by_category():
    json_dir = "data/crawler_data"
    
    # Only include consent management extensions and baseline
    banner_profiles = [
        'no_extensions',
        'consent_o_matic_opt_out',
        'consent_o_matic_opt_in',
        'super_agent_opt_out',
        'super_agent_opt_in'
    ]
    
    # Get list of actually existing profiles
    existing_profiles = {}
    for profile_id in banner_profiles:
        if profile_id in DISPLAY_NAMES:
            profile_path = os.path.join(json_dir, profile_id)
            if os.path.exists(profile_path):
                existing_profiles[profile_id] = DISPLAY_NAMES[profile_id]

    # Get domains that loaded successfully AND had banners removed
    successful_domains = get_successful_domains_with_removals()
    
    # Load cookies for existing profiles
    profile_cookies = {}
    for profile_id in existing_profiles:
        print(f"\nLoading cookies for {existing_profiles[profile_id]}...")
        profile_cookies[profile_id] = load_cookies_from_json(json_dir, profile_id, successful_domains)
    
    # Define cookie categories
    cookie_categories = ['Necessary', 'Functional', 'Analytics', 'Advertisement', 'Performance', 'Other', 'Unknown']
    
    # Calculate similarity matrices for each category
    similarity_matrices = {category: defaultdict(dict) for category in cookie_categories}
    print("\nCalculating similarities between profiles for each cookie category...")
    
    for category in cookie_categories:
        print(f"\nProcessing {category} cookies...")
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
                            similarity = calculate_cookie_similarity_by_category(cookies1, cookies2, category)
                            total_similarity += similarity
                            domain_count += 1
                    
                    avg_similarity = total_similarity / domain_count if domain_count > 0 else 0
                    similarity_matrices[category][profile1][profile2] = avg_similarity
    
    # Create ordered list of profiles (baseline first, then extensions)
    ordered_profiles = ['no_extensions'] + [p for p in banner_profiles if p != 'no_extensions' and p in existing_profiles]
    
    # Create plots for each category
    for category in cookie_categories:
        fig, ax = plt.subplots(figsize=(15, 12))
        
        similarity_values = np.zeros((len(ordered_profiles), len(ordered_profiles)))
        for i, p1 in enumerate(ordered_profiles):
            for j, p2 in enumerate(ordered_profiles):
                if i == j:
                    similarity_values[i][j] = 1.0
                else:
                    similarity_values[i][j] = similarity_matrices[category][p1][p2]
        
        # Plot heatmap
        im = ax.imshow(similarity_values, cmap='YlOrRd')
        plt.colorbar(im, ax=ax, label='Similarity Score')
        
        # Adjust labels
        ax.set_xticks(range(len(ordered_profiles)))
        ax.set_xticklabels([DISPLAY_NAMES[p] for p in ordered_profiles], 
                          rotation=45, ha='right', rotation_mode='anchor')
        ax.set_yticks(range(len(ordered_profiles)))
        ax.set_yticklabels([DISPLAY_NAMES[p] for p in ordered_profiles])
        
        # Add text annotations
        for i in range(len(ordered_profiles)):
            for j in range(len(ordered_profiles)):
                value = similarity_values[i, j]
                text_color = 'white' if value > 0.85 else 'black'
                
                text = ax.text(j, i, f'{value:.3f}',
                             ha='center', va='center',
                             color=text_color,
                             fontsize=10,
                             fontweight='bold',
                             path_effects=[
                                 Stroke(linewidth=1.2, foreground='white'),
                                 Normal()
                             ])
        
        plt.title(f'{category} cookies')
        plt.tight_layout()
        
        # Save plot
        filename = f'cookie_extension_similarity_{category.lower()}_successful_removals.png'
        output_path = os.path.join(output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
        plt.close()

if __name__ == "__main__":
    analyze_banner_extension_similarities_by_category()