import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.third_party.third_party_domain_prevalence import get_third_party_domains, load_tranco_ranks, get_successful_domains
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

def load_cookies_from_json(json_dir, profile, domains):
    """Load cookies from JSON files for a given profile."""
    cookies_dict = {}
    
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        return cookies_dict

    for domain in domains:
        file_path = os.path.join(json_dir, profile, f"{domain}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # The cookies are stored under data['cookies']['1']
                    if 'cookies' in data and '1' in data['cookies']:
                        cookies_dict[domain] = data['cookies']['1']
                    else:
                        cookies_dict[domain] = []
            except json.JSONDecodeError:
                cookies_dict[domain] = []
    return cookies_dict

def calculate_cookie_similarity(cookies1, cookies2):
    """Calculate Jaccard similarity between two sets of cookies."""
    try:
        # Convert cookie lists to sets of cookie names
        names1 = set(cookie.get('name', '') for cookie in cookies1)
        names2 = set(cookie.get('name', '') for cookie in cookies2)
        
        # Calculate Jaccard similarity
        if not names1 and not names2:  # Both empty
            return 1.0
        intersection = len(names1 & names2)
        union = len(names1 | names2)
        return intersection / union
    except Exception as e:
        print(f"Error calculating similarity: {e}")
        print(f"cookies1: {cookies1}")
        print(f"cookies2: {cookies2}")
        return 0.0


def main():
    json_dir = "data/crawler_data"
    successful_domains = get_successful_domains()
    
    # Get only cookie-related profiles
    cookie_profiles = PROFILE_GROUPS["Cookie Extensions"]
    
    # Load cookies for cookie profiles
    print("\nLoading cookies for cookie management extensions...")
    profile_cookies = {}
    for profile in cookie_profiles:
        profile_cookies[profile] = load_cookies_from_json(json_dir, profile, successful_domains)
    
    # Calculate average similarities between profiles
    print("\nCalculating average similarities...")
    similarity_matrix = pd.DataFrame(index=cookie_profiles, columns=cookie_profiles)
    
    for profile1 in tqdm(cookie_profiles):
        for profile2 in cookie_profiles:
            similarities = []
            # Only process shared domains
            shared_domains = profile_cookies[profile1].keys() & profile_cookies[profile2].keys()
            
            for domain in shared_domains:
                cookies1 = profile_cookies[profile1][domain]
                cookies2 = profile_cookies[profile2][domain]
                
                if cookies1 or cookies2:  # Skip if both are empty
                    similarity = calculate_cookie_similarity(cookies1, cookies2)
                    similarities.append(similarity)
            
            # Handle the case where there are no similarities
            if not similarities:
                avg_similarity = 0.0
            else:
                avg_similarity = float(sum(similarities)) / len(similarities)
            
            similarity_matrix.loc[profile1, profile2] = avg_similarity
    
    # Ensure all values are valid numbers
    similarity_matrix = similarity_matrix.fillna(0.0)
    
    # Convert profile names to display names
    similarity_matrix.index = [DISPLAY_NAMES[p] for p in similarity_matrix.index]
    similarity_matrix.columns = [DISPLAY_NAMES[p] for p in similarity_matrix.columns]
    
    # Create the heatmap
    plt.figure(figsize=(12, 10))
    sns.heatmap(similarity_matrix, 
                cmap='RdYlBu_r',
                vmin=0, 
                vmax=1,
                square=True,
                annot=True,
                fmt='.2f',
                cbar_kws={'label': 'Average Similarity Score'})
    
    plt.title('Average Cookie Similarity Between Cookie Management Extensions', pad=20)
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Create directory and save
    os.makedirs('analysis/graphs/similarity', exist_ok=True)
    plt.savefig('analysis/graphs/similarity/profile_similarity_heatmap_cookies.png', 
                dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    main() 