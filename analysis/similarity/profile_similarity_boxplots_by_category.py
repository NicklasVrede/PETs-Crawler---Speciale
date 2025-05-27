import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys
import json
from collections import defaultdict
from tqdm import tqdm

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS
from analysis.third_party.third_party_domain_prevalence import get_successful_domains

 # Create plots for each profile
group_order = ["Baseline Profile", "Traditional PETs", "Cookie Extensions", "Other"]
    

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

    for json_file in tqdm(json_files, desc=f"Loading cookies for {profile}", leave=False):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                domain = data.get('domain', os.path.basename(json_file)[:-5])
                
                if 'cookies' in data and '1' in data['cookies']:
                    for cookie in data['cookies']['1']:
                        if ('classification' in cookie and 
                            cookie['classification'].get('category') not in ['Unknown', 'Other']):
                            cookies_by_domain[domain].append({
                                'name': cookie.get('name'),
                                'domain': cookie.get('domain'),
                                'path': cookie.get('path'),
                                'category': cookie['classification'].get('category')
                            })
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            
    return cookies_by_domain

def calculate_cookie_similarity_by_category(cookies1, cookies2):
    """Calculate Jaccard similarity between two sets of cookies by category."""
    # Group cookies by category
    cookies1_by_category = defaultdict(set)
    cookies2_by_category = defaultdict(set)
    
    for cookie in cookies1:
        category = cookie['category']
        cookies1_by_category[category].add((cookie['name'], cookie['domain'], cookie['path']))
    
    for cookie in cookies2:
        category = cookie['category']
        cookies2_by_category[category].add((cookie['name'], cookie['domain'], cookie['path']))
    
    # Calculate similarity for each category
    all_categories = set(cookies1_by_category.keys()) | set(cookies2_by_category.keys())
    if not all_categories:
        return 1.0  # If no categorized cookies in either set
    
    total_similarity = 0
    for category in all_categories:
        set1 = cookies1_by_category[category]
        set2 = cookies2_by_category[category]
        
        if not set1 and not set2:
            continue  # Skip empty categories
            
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        if union > 0:
            total_similarity += intersection / union
    
    return total_similarity / len(all_categories) if all_categories else 0

def main():
    json_dir = "data/crawler_data"
    successful_domains = get_successful_domains()
    print(f"\nFound {len(successful_domains)} domains that loaded successfully across all profiles")
    
    # Get all profiles
    all_profiles = []
    for group in PROFILE_GROUPS.values():
        all_profiles.extend(group)
    
    # Load cookies for all profiles
    print("\nLoading cookies for all profiles...")
    profile_cookies = {}
    for profile in all_profiles:
        profile_cookies[profile] = load_cookies_from_json(json_dir, profile, successful_domains)
    
    # Calculate similarities for each domain
    similarity_scores = []
    print("\nCalculating similarities...")
    for profile1 in tqdm(all_profiles, desc="Processing profiles"):
        for profile2 in all_profiles:
            for domain in profile_cookies[profile1].keys() & profile_cookies[profile2].keys():
                cookies1 = profile_cookies[profile1][domain]
                cookies2 = profile_cookies[profile2][domain]
                
                if cookies1 or cookies2:
                    if profile1 == profile2:
                        similarity = 1.0
                    else:
                        similarity = calculate_cookie_similarity_by_category(cookies1, cookies2)
                    similarity_scores.append({
                        'domain': domain,
                        'profile1': profile1,
                        'profile2': profile2,
                        'similarity': similarity
                    })
    
    # Convert to DataFrame
    similarity_df = pd.DataFrame(similarity_scores)
    
    # Get unique categories from the data
    all_categories = set()
    for profile in profile_cookies.values():
        for domain_cookies in profile.values():
            for cookie in domain_cookies:
                all_categories.add(cookie['category'])
    
    # Create plots for each category
    for category in all_categories:
        # Calculate similarities for this category only
        category_scores = []
        for profile1 in tqdm(all_profiles, desc=f"Processing {category} category"):
            for profile2 in all_profiles:
                for domain in profile_cookies[profile1].keys() & profile_cookies[profile2].keys():
                    cookies1 = [c for c in profile_cookies[profile1][domain] if c['category'] == category]
                    cookies2 = [c for c in profile_cookies[profile2][domain] if c['category'] == category]
                    
                    if cookies1 or cookies2:
                        if profile1 == profile2:
                            similarity = 1.0
                        else:
                            similarity = calculate_cookie_similarity_by_category(cookies1, cookies2)
                        category_scores.append({
                            'domain': domain,
                            'profile1': profile1,
                            'profile2': profile2,
                            'similarity': similarity
                        })
        
        category_df = pd.DataFrame(category_scores)
        
        # Create directory for similarity plots if it doesn't exist
        os.makedirs('analysis/graphs/similarity/by_category', exist_ok=True)
        
        # Create plots for each profile within this category
        for profile1 in all_profiles:
            plt.figure(figsize=(12, 6))
            profile_data = category_df[category_df['profile1'] == profile1]
            
            # Create a mapping of profile names to their groups for sorting
            profile_to_group = {}
            for group, profiles in PROFILE_GROUPS.items():
                for profile in profiles:
                    profile_to_group[profile] = group
            
            # Sort profiles by group order and names within groups
            sorted_profiles = sorted(profile_data['profile2'].unique(), 
                                   key=lambda x: (group_order.index(profile_to_group[x]), DISPLAY_NAMES[x]))
            
            # Create boxplot with black and white style
            sns.boxplot(data=profile_data, x='profile2', y='similarity', 
                        order=sorted_profiles,
                        color='white',          
                        flierprops={'marker': '.', 'markerfacecolor': 'black', 'markersize': 4},  
                        medianprops={'color': 'black'},  
                        boxprops={'edgecolor': 'black'},  
                        whiskerprops={'color': 'black'},  
                        capprops={'color': 'black'},      
                        showfliers=False)
            
            # Define mean line color (same as cookie distribution)
            mean_color = '#E68080'  # Light coral red
            
            # Add mean lines
            means = profile_data.groupby('profile2')['similarity'].mean()
            for i, profile in enumerate(sorted_profiles):
                mean = means[profile]
                plt.hlines(y=mean, xmin=i-0.4, xmax=i+0.4, 
                          color=mean_color, linestyles='--', linewidth=1, alpha=0.8)
            
            # Customize plot
            plt.xticks(range(len(sorted_profiles)), 
                       [DISPLAY_NAMES[p] for p in sorted_profiles],
                       rotation=45, ha='right', fontsize=10)
            
            # Set y-axis limits to make room for labels
            plt.ylim(-0.1, 1.18)
            y_min, y_max = plt.ylim()
            label_height = 1.12
            
            # Add group dividers and labels
            current_position = 0
            for group_name in group_order:
                group_profiles = [p for p in sorted_profiles if profile_to_group[p] == group_name]
                if group_profiles:
                    group_start = current_position
                    group_end = current_position + len(group_profiles) - 1
                    
                    # Add vertical divider line if not the last group
                    if group_end < len(sorted_profiles) - 1:
                        plt.axvline(x=group_end + 0.5, color='black', linestyle=':', alpha=0.7)
                     
                    # Add group label
                    label_position = (group_start + group_end) / 2
                    plt.text(label_position, label_height,
                            group_name,
                            ha='center', va='bottom',
                            fontsize=12,
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
                    
                    current_position += len(group_profiles)
            
            # Add grid
            plt.grid(axis='y', linestyle='--', alpha=0.3)
            
            # Update title to include category
            plt.title(f'Cookie Similarity - {category} Cookies - {DISPLAY_NAMES[profile1]}', fontsize=14)
            
            # Save plot with category in filename
            plt.savefig(
                f'analysis/graphs/similarity/by_category/profile_similarity_{category.lower()}_{profile1}.png', 
                dpi=300, bbox_inches='tight'
            )
            plt.close()

if __name__ == "__main__":
    main() 