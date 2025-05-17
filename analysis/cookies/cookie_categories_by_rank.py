import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import rgb2hex

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

def get_rank_bucket_label(rank):
    """Convert a rank to a bucket label"""
    for start, end in RANK_BUCKETS:
        if start <= rank <= end:
            if start < 1000:
                start_label = str(start)
            else:
                start_label = f"{start//1000}k"
            if end < 1000:
                end_label = str(end)
            else:
                end_label = f"{end//1000}k"
            return f"[{start_label}-{end_label}]"
    return "unknown"

# Add rank bucket column
df_loaded['rank_bucket'] = df_loaded['rank'].apply(get_rank_bucket_label)
rank_order = [get_rank_bucket_label(bucket[0]) for bucket in RANK_BUCKETS]

# Define profiles to exclude
excluded_profiles = {'ublock_origin_lite', 'disconnect', 'cookie_cutter'}

# Define categories and their display names - including Others/Unknown
categories = [
    ('necessary_cookies', 'Necessary'),
    ('functional_cookies', 'Functional'),
    ('performance_cookies', 'Performance'),
    ('advertising_cookies', 'Advertising'),
    ('analytics_cookies', 'Analytics'),
    ('others_and_unknown', 'Others/Unknown')  # Added new category
]

# Calculate combined Others/Unknown cookies (before the plotting loop)
df_loaded['others_and_unknown'] = df_loaded['other_cookies'] + df_loaded['unknown_cookies']

# Get colors from the tab20 colormap (which has 20 colors)
colors = [rgb2hex(plt.cm.tab20(i)) for i in range(20)]

# Define specific markers and colors for each profile using tab20 colors
profile_styles = {
    'accept_all_cookies': {'marker': 'o', 'color': colors[0]},      # tab20 blue
    'adblock': {'marker': '^', 'color': colors[2]},                # tab20 green
    'adblock_plus': {'marker': '^', 'color': colors[4]},          # tab20 red
    'adguard': {'marker': 'D', 'color': colors[6]},               # tab20 purple
    'consent_o_matic_opt_in': {'marker': 'v', 'color': colors[8]},  # tab20 brown
    'consent_o_matic_opt_out': {'marker': 'v', 'color': colors[10]}, # tab20 pink
    'decentraleyes': {'marker': '>', 'color': colors[12]},          # tab20 gray
    'ghostery_tracker_&_ad_blocker': {'marker': 'o', 'color': colors[14]},  # tab20 olive
    'ghostery_tracker_&_ad_blocker_only_never_consent': {'marker': 'o', 'color': colors[16]},  # tab20 cyan
    'i_dont_care_about_cookies': {'marker': 'o', 'color': colors[18]},  # tab20 lime
    'no_extensions': {'marker': 'o', 'color': 'black'},            # Black (Baseline)
    'privacy_badger': {'marker': '*', 'color': colors[1]},         # tab20 light blue
    'super_agent_opt_in': {'marker': 'o', 'color': colors[3]},     # tab20 light green
    'super_agent_opt_out': {'marker': 'o', 'color': colors[5]},    # tab20 light red
    'ublock': {'marker': '+', 'color': colors[7]},                # tab20 light purple
}

# Filter the dataframe to exclude unwanted profiles
df_loaded = df_loaded[~df_loaded['profile'].isin(excluded_profiles)]

# Define custom x-axis positions - slightly wider spacing for larger buckets
x_positions = [0, 0.4, 0.8, 1.5, 2.3, 3.0]  # Manually adjusted positions

# Define which profiles to include in each plot
pets_profiles = set(PROFILE_GROUPS['Traditional PETs'] + PROFILE_GROUPS['Baseline Profile'])
cookie_profiles = set(PROFILE_GROUPS['Cookie Extensions'] + PROFILE_GROUPS['Other'] + PROFILE_GROUPS['Baseline Profile'])

# Create two sets of figures
for plot_type, profiles_to_include in [
    ('PETs', pets_profiles),
    ('Cookie Extensions', cookie_profiles)
]:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    
    for idx, (category_col, category_name) in enumerate(categories):
        # Calculate max y-value for this category across both PETs and Extensions
        max_y = 0
        for _, all_profiles in [('PETs', pets_profiles), ('Cookie Extensions', cookie_profiles)]:
            df_plot_max = df_loaded[df_loaded['profile'].isin(all_profiles)]
            means = df_plot_max.groupby(['profile', 'rank_bucket'])[category_col].mean()
            max_y = max(max_y, means.max())

        # Plot data for current profile type
        df_plot = df_loaded[df_loaded['profile'].isin(profiles_to_include)]
        ax = axes[idx]
        
        # Calculate means for each profile and rank bucket
        means = df_plot.groupby(['profile', 'rank_bucket'])[category_col].mean().reset_index()
        
        # Plot for each profile
        for profile in df_plot['profile'].unique():
            profile_data = means[means['profile'] == profile]
            style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})
            
            # Map rank buckets to custom x positions
            profile_x_positions = []
            profile_y_values = []
            
            for bucket in rank_order:
                bucket_data = profile_data[profile_data['rank_bucket'] == bucket]
                if not bucket_data.empty:
                    pos_idx = rank_order.index(bucket)
                    profile_x_positions.append(x_positions[pos_idx])
                    profile_y_values.append(bucket_data[category_col].iloc[0])
            
            ax.plot(profile_x_positions, profile_y_values,
                   marker=style['marker'],
                   color=style['color'],
                   markersize=8,
                   label=DISPLAY_NAMES.get(profile, profile),
                   alpha=0.8,
                   markeredgecolor='black',
                   markeredgewidth=1.0,
                   linewidth=1.5)

        # Customize subplot
        ax.set_title(category_name, pad=10)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([rb.replace('Top ', '') for rb in rank_order], rotation=45)
        ax.set_ylabel('Average number of cookies' if idx % 3 == 0 else '')
        
        # Set y-axis limits for this category
        ax.set_ylim(bottom=0, top=max_y * 1.1)  # Add 10% padding

        # Only show legend for the last subplot
        if idx == len(categories) - 1:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.suptitle(f'Cookies observed per profile based by rank and type - {plot_type}', 
                 y=1.00)  # Reduced y value to move title closer
    
    plt.tight_layout(
        rect=[0, 0, 0.92, 0.94],  # Adjusted top margin to be smaller
        h_pad=0.2,
        w_pad=0.2
    )

    # Save with less padding
    plt.savefig(
        f'analysis/graphs/cookie_categories_by_rank_{plot_type.lower().replace(" ", "_")}.png',
        bbox_inches='tight',
        dpi=300,
        pad_inches=0.1  # Reduced padding
    )
    plt.close()

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