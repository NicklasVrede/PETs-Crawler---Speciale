import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

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

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure we only use profiles that exist in our data
all_profiles = [p for p in ordered_profiles if p in df_loaded['profile'].unique()]

def create_violin_plot(data, metric, title, ylabel, output_file):
    plt.figure(figsize=(16, 8))
    
    # Calculate y_max first before using it
    y_max = data[metric].max()
    
    # Create violin plot
    sns.violinplot(data=data, x='profile', y=metric,
                   order=all_profiles,
                   inner='box',
                   cut=0,
                   width=0.7)
    
    # Add small n=XXX counts below each violin
    for idx, profile in enumerate(all_profiles):
        profile_total = data[data['profile'] == profile][metric].sum()
        plt.text(idx, -0.5,  # Position below the violins
                f'n={profile_total:,.0f}',
                ha='center', va='top', fontsize=8)
    
    plt.ylabel(ylabel, fontsize=14, labelpad=10)
    plt.xlabel('', fontsize=14, labelpad=10)
    
    # Add group labels above the plot (adjusted position)
    current_position = 0
    for group_name, group_profiles in PROFILE_GROUPS.items():
        group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
        if group_profiles_in_data:
            group_start = current_position
            group_end = current_position + len(group_profiles_in_data) - 1
            label_position = (group_start + group_end) / 2
            plt.text(label_position, y_max * 1.1, group_name,
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
    
    # Use display names for x-tick labels
    plt.xticks(range(len(all_profiles)), 
              [DISPLAY_NAMES.get(p, p) for p in all_profiles],
              rotation=45, ha='right', fontsize=10)
    
    # Add grid for better readability
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Adjust layout
    plt.subplots_adjust(bottom=0.2)
    
    # Save the plot
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

# Create Local Storage plot
create_violin_plot(
    data=df_loaded,
    metric='local_storage_potential_identifiers',
    title='Potential Local Storage Identifiers per Page by Profile',
    ylabel='Number of Potential Local Storage Identifiers',
    output_file='analysis/graphs/local_storage_identifiers_violin.png'
)

# Create Session Storage plot
create_violin_plot(
    data=df_loaded,
    metric='session_storage_potential_identifiers',
    title='Potential Session Storage Identifiers per Page by Profile',
    ylabel='Number of Potential Session Storage Identifiers',
    output_file='analysis/graphs/session_storage_identifiers_violin.png'
)

# Print summary statistics for both metrics
print("\nSummary Statistics:")
for profile in all_profiles:
    print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
    
    # Local Storage statistics
    local_data = df_loaded[df_loaded['profile'] == profile]['local_storage_potential_identifiers']
    print("\nLocal Storage:")
    print(f"  Median: {local_data.median():.1f}")
    print(f"  Mean: {local_data.mean():.1f}")
    print(f"  Q1: {local_data.quantile(0.25):.1f}")
    print(f"  Q3: {local_data.quantile(0.75):.1f}")
    print(f"  Min: {local_data.min():.1f}")
    print(f"  Max: {local_data.max():.1f}")
    
    # Session Storage statistics
    session_data = df_loaded[df_loaded['profile'] == profile]['session_storage_potential_identifiers']
    print("\nSession Storage:")
    print(f"  Median: {session_data.median():.1f}")
    print(f"  Mean: {session_data.mean():.1f}")
    print(f"  Q1: {session_data.quantile(0.25):.1f}")
    print(f"  Q3: {session_data.quantile(0.75):.1f}")
    print(f"  Min: {session_data.min():.1f}")
    print(f"  Max: {session_data.max():.1f}") 