import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

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

# Get all unique profiles
all_profiles = df_loaded['profile'].unique()
print(f"Found {len(all_profiles)} unique profiles: {', '.join(all_profiles)}")

# Define cookie categories to analyze
cookie_categories = [
    'necessary_cookies',
    'functional_cookies',
    'advertising_cookies',
    'analytics_cookies',
    'performance_cookies',
    'other_cookies',
    'unknown_cookies'
]

# Check which categories are actually in the dataset
available_categories = [col for col in cookie_categories if col in df_loaded.columns]
if len(available_categories) < len(cookie_categories):
    missing = set(cookie_categories) - set(available_categories)
    print(f"Warning: The following cookie categories are not in the dataset: {', '.join(missing)}")
    cookie_categories = available_categories

# Analyze each profile separately
profile_stats = []

for profile in all_profiles:
    # Get data for this profile
    profile_data = df_loaded[df_loaded['profile'] == profile]
    domains_count = len(profile_data['domain'].unique())
    print(f"{profile}: Successfully loaded {domains_count} domains")
    
    # Calculate cookie stats for this profile
    for category in cookie_categories:
        if category in profile_data.columns:
            # Use mean count of cookies in this category
            mean_count = profile_data[category].mean()
            
            profile_stats.append({
                'profile': profile,
                'category': category,
                'mean': mean_count,
                'domains_count': domains_count
            })

# Convert to DataFrame for easier analysis
stats_df = pd.DataFrame(profile_stats)

# Create readable labels for x-axis
profile_labels = {}
for profile in all_profiles:
    # Generate readable labels for all profiles
    if profile == 'no_extensions':
        profile_labels[profile] = 'No Extensions'
    else:
        # Format other profile names to be more readable
        profile_labels[profile] = ' '.join(word.capitalize() for word in profile.replace('_', ' ').split())

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure we only use profiles that exist in our data
all_profiles = [p for p in ordered_profiles if p in df_loaded['profile'].unique()]

# Create the grouped bar chart
plt.figure(figsize=(16, 8))

# Set up the bar positions
x = np.arange(len(all_profiles))
bar_width = 0.8 / len(cookie_categories)
total_width = bar_width * len(cookie_categories)

# Create a color palette - use Dark2 palette
colors = sns.color_palette("Dark2", len(cookie_categories))

# Plot each category as a group of bars
for i, category in enumerate(cookie_categories):
    category_data = stats_df[stats_df['category'] == category]
    category_means = []
    
    for profile in all_profiles:
        profile_category_data = category_data[category_data['profile'] == profile]
        if not profile_category_data.empty:
            category_means.append(profile_category_data['mean'].values[0])
        else:
            category_means.append(0)
    
    # Calculate position for this group of bars
    pos = x - total_width/2 + i * bar_width + bar_width/2
    
    # Create readable label
    label = category.replace('_', ' ').title().replace('Cookies', '')
    
    bars = plt.bar(pos, category_means, width=bar_width, label=label, color=colors[i], alpha=1.0)  # Set alpha to 1.0 for Dark2
    
    # Add value labels on top of each bar
    for j, bar in enumerate(bars):
        height = bar.get_height()
        if height > 0.1:  # Only add labels for non-trivial values
            plt.text(bar.get_x() + bar.get_width()/2, height + 0.1,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9, rotation=90)

# Add group labels above the bars with more space from title
current_position = 0
y_max = plt.gca().get_ylim()[1]
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.01, group_name,  # Reduced from 1.02 to 1.01
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

# Set title with more padding and simplified text
plt.title('Cookie Categories per Profile\n(For domains that loaded successfully across all profiles \n and exluding "Others" and "Unknown")', 
          fontsize=16, pad=40)

# Customize the plot
plt.ylabel('Average Cookie Count', fontsize=14, labelpad=10)
plt.xlabel('Browser Profile', fontsize=14, labelpad=10)  # Added labelpad
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Use display names for x-tick labels with more space
plt.xticks(x, [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles], 
          rotation=45, ha='right', fontsize=10)

# Adjust layout to prevent label cutoff
plt.subplots_adjust(bottom=0.2)  # Increased bottom margin for x-labels
plt.tight_layout()

# Verify all profiles are included
print("Profiles being plotted:", all_profiles)  # Debug line to check if Super Agent profiles are in the data

# Move legend inside the plot
ax = plt.gca()
plt.legend(title='Cookie Category', 
          bbox_to_anchor=(1, 1),  # Position at the right edge of the plot
          loc='upper right',
          bbox_transform=ax.transAxes)  # Use axes coordinates

# Ensure y-axis starts at 0
plt.ylim(bottom=0)

# Adjust layout with even more space for title
plt.subplots_adjust(top=0.85)  # Reduced from 0.88 to 0.85 to prevent title cutoff

plt.savefig('analysis/graphs/cookie_purpose_categories_comparison_all.png', dpi=300, bbox_inches='tight')
plt.show() 