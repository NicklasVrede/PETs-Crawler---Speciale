import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from data.analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Get domains that loaded successfully across all profiles
all_profiles = df_loaded['profile'].unique()
successful_domains = set()
for domain in df_loaded['domain'].unique():
    if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
           for profile in all_profiles):
        successful_domains.add(domain)

# Filter for only those domains
df_loaded = df_loaded[df_loaded['domain'].isin(successful_domains)]

# Calculate first party cookies (total - third party), ensuring no negative values
df_loaded['first_party_cookies'] = np.maximum(
    0, 
    df_loaded['unique_cookies'] - df_loaded['third_party_cookies']
)

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure we only use profiles that exist in our data
all_profiles = [p for p in ordered_profiles if p in df_loaded['profile'].unique()]

# Create the stacked bar chart
plt.figure(figsize=(16, 8))

# Calculate means for each profile
means_data = []
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]
    means_data.append({
        'profile': profile,
        'first_party_mean': profile_data['first_party_cookies'].mean(),
        'third_party_mean': profile_data['third_party_cookies'].mean()
    })

# Convert to DataFrame
means_df = pd.DataFrame(means_data)

# Create the stacked bar chart
x = np.arange(len(all_profiles))
width = 0.8

# Create bars
plt.bar(x, means_df['first_party_mean'], width, 
        label='First Party Cookies', color='lightblue')
plt.bar(x, means_df['third_party_mean'], width,
        bottom=means_df['first_party_mean'], 
        label='Third Party Cookies', color='coral')

# Add value labels on the bars
for i in range(len(x)):
    first_party = means_df['first_party_mean'].iloc[i]
    third_party = means_df['third_party_mean'].iloc[i]
    total = first_party + third_party
    
    # Add first party value in the middle of its section
    if first_party > 0.1:
        plt.text(i, first_party/2, f'{first_party:.1f}', 
                ha='center', va='center')
    
    # Add third party value in the middle of its section
    if third_party > 0.1:
        plt.text(i, first_party + third_party/2, f'{third_party:.1f}', 
                ha='center', va='center')
    
    # Add total on top
    if total > 0.1:
        plt.text(i, total + 0.5, f'Total: {total:.1f}', 
                ha='center', va='bottom')

# Add group labels above the bars
current_position = 0
y_max = plt.gca().get_ylim()[1]
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.01, group_name,
                ha='center', va='bottom', fontsize=12,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
        
        current_position += len(group_profiles_in_data)

# Add vertical lines to separate groups
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        current_position += len(group_profiles_in_data)
        if current_position < len(all_profiles):
            plt.axvline(x=current_position - 0.5, color='black', linestyle=':', alpha=0.7)

# Customize the plot
plt.title('Average Number of Cookies per Profile\n(For domains that loaded successfully across all profiles)',
          fontsize=16, pad=40)
plt.ylabel('Average Cookie Count', fontsize=14, labelpad=10)
plt.xlabel('Browser Profile', fontsize=14, labelpad=10)
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Use display names for x-tick labels
plt.xticks(x, [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
          rotation=45, ha='right', fontsize=10)

# Adjust layout
plt.subplots_adjust(bottom=0.2, top=0.85)

# Add legend
plt.legend()

plt.savefig('cookie_totals_comparison.png', dpi=300, bbox_inches='tight')
plt.show() 