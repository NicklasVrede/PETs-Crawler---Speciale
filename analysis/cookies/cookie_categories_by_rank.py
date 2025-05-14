import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Define rank buckets
def get_rank_bucket(rank):
    if rank <= 10:
        return 'Top 10'
    elif rank <= 25:
        return 'Top 25'
    elif rank <= 50:
        return 'Top 50'
    else:
        return 'Top 51-100'

# Add rank bucket column
df_loaded['rank_bucket'] = df_loaded['rank'].apply(get_rank_bucket)
rank_order = ['Top 10', 'Top 25', 'Top 50', 'Top 51-100']

# Define categories and their display names - including Performance
categories = [
    ('necessary_cookies', 'Necessary'),
    ('functional_cookies', 'Functional'),
    ('performance_cookies', 'Performance'),
    ('advertising_cookies', 'Advertising'),
    ('analytics_cookies', 'Analytics')
]

# Define specific markers and colors for each profile
profile_styles = {
    'accept_all_cookies': {'marker': 'o', 'color': '#1f77b4'},  # Blue
    'i_dont_care_about_cookies': {'marker': 'o', 'color': '#2ca02c'},  # Green
    'baseline_profile': {'marker': 's', 'color': '#ff7f0e'},  # Orange
    'adblock': {'marker': '^', 'color': '#d62728'},  # Red
    'adblock_plus': {'marker': '^', 'color': '#9467bd'},  # Purple
    'adguard': {'marker': 'D', 'color': '#8c564b'},  # Brown
    'consent_o_matic_opt_in': {'marker': 'v', 'color': '#e377c2'},  # Pink
    'consent_o_matic_opt_out': {'marker': 'v', 'color': '#7f7f7f'},  # Gray
    'cookie_cutter': {'marker': '<', 'color': '#bcbd22'},  # Yellow-green
    'decentraleyes': {'marker': '>', 'color': '#17becf'},  # Cyan
    'disconnect': {'marker': 'p', 'color': '#393b79'},  # Dark blue
    'ghostery': {'marker': 'h', 'color': '#637939'},  # Olive
    'privacy_badger': {'marker': '*', 'color': '#8c6d31'},  # Gold
    'super_agent': {'marker': 'X', 'color': '#843c39'},  # Dark red
    'ublock': {'marker': 'P', 'color': '#7b4173'},  # Dark purple
    'ublock_origin_lite': {'marker': 'P', 'color': '#5254a3'},  # Blue-purple
}

# Create figure with subplots - adjusted for 5 categories
fig, axes = plt.subplots(2, 3, figsize=(20, 10))  # Changed back to 2x3 grid for 5 plots
axes = axes.flatten()

# Calculate means for each profile, rank bucket, and category
for idx, (category_col, category_name) in enumerate(categories):
    ax = axes[idx]
    
    # Calculate means for each profile and rank bucket
    means = df_loaded.groupby(['profile', 'rank_bucket'])[category_col].mean().reset_index()
    
    # Plot for each profile
    for profile in df_loaded['profile'].unique():
        profile_data = means[means['profile'] == profile]
        style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})  # Default style
        
        # Convert rank buckets to numeric x-positions
        x_positions = [rank_order.index(rb) for rb in profile_data['rank_bucket']]
        
        # Plot points with profile-specific style
        ax.scatter(x_positions, profile_data[category_col], 
                  marker=style['marker'],
                  color=style['color'],
                  s=30,
                  label=DISPLAY_NAMES.get(profile, profile),
                  alpha=0.8,
                  edgecolors='black',
                  linewidth=0.5)

    # Customize subplot
    ax.set_title(category_name, pad=10)
    ax.set_xticks(range(len(rank_order)))
    ax.set_xticklabels([rb.replace('Top ', '') for rb in rank_order], rotation=0)
    ax.set_ylabel('Average number of cookies' if idx % 3 == 0 else '')
    # ax.grid(True, alpha=0.3)  # Removed grid lines
    
    # Only show legend for the last subplot
    if idx == len(categories) - 1:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Set y-axis to start at 0
    ax.set_ylim(bottom=0)

# Remove the last (empty) subplot since we only have 5 categories
axes[-1].remove()  # Remove the 6th (unused) subplot

# Adjust layout
plt.suptitle('Cookie Categories by Website Rank', fontsize=16, y=1.0)
plt.subplots_adjust(top=0.93)
plt.tight_layout()

# Save the plot
plt.savefig('cookie_categories_by_rank.png', dpi=300, bbox_inches='tight')
plt.show()

# Print average values
print("\nAverage cookies by rank bucket and category:")
for rank in rank_order:
    print(f"\nRank bucket: {rank}")
    rank_data = df_loaded[df_loaded['rank_bucket'] == rank]
    for col, title in categories:
        print(f"{title}:")
        for profile in df_loaded['profile'].unique():
            profile_mean = rank_data[rank_data['profile'] == profile][col].mean()
            print(f"  {DISPLAY_NAMES.get(profile, profile)}: {profile_mean:.1f}") 