import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys
from tqdm import tqdm

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS
from analysis.third_party.third_party_domain_prevalence import get_successful_domains
# Import the functions we'll reuse from the boxplot script
from analysis.similarity.profile_similarity_boxplots import load_cookies_from_json, calculate_cookie_similarity

def main():
    json_dir = "data/crawler_data"
    successful_domains = get_successful_domains()
    
    # Get all profiles
    all_profiles = []
    for group in PROFILE_GROUPS.values():
        all_profiles.extend(group)
    
    # Load cookies for all profiles
    print("\nLoading cookies for all profiles...")
    profile_cookies = {}
    for profile in all_profiles:
        profile_cookies[profile] = load_cookies_from_json(json_dir, profile, successful_domains)
    
    # Calculate average similarities between profiles
    print("\nCalculating average similarities...")
    similarity_matrix = pd.DataFrame(index=all_profiles, columns=all_profiles)
    
    for profile1 in tqdm(all_profiles):
        for profile2 in all_profiles:
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
                cmap='RdYlBu_r',  # Red-Yellow-Blue colormap, reversed
                vmin=0, 
                vmax=1,
                square=True,
                annot=True,      # Show numbers in cells
                fmt='.2f',       # Format numbers to 2 decimal places
                cbar_kws={'label': 'Average Similarity Score'})
    
    plt.title('Average Cookie Similarity Between Profiles', pad=20)
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right', fontsize=16)
    plt.yticks(rotation=0, fontsize=16)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Create directory and save
    os.makedirs('analysis/graphs/similarity', exist_ok=True)
    plt.savefig('analysis/graphs/similarity/profile_similarity_heatmap.png', 
                dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    main() 