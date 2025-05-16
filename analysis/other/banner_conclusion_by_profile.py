import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Order the profiles in a meaningful way using imported groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure that both columns exist
required_columns = ['banner_conclusion', 'page_status', 'domain']
missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    print(f"Error: The following required columns are missing: {missing_columns}")
    exit()

# Filter domains where all profiles have "loaded" page_status
# First, get all available profiles in the dataset
available_profiles = df['profile'].unique()

# Find domains that loaded successfully for all profiles
loaded_domains = set()
domains_to_check = set(df['domain'].unique())

for domain in domains_to_check:
    domain_profiles = df[df['domain'] == domain]['profile'].unique()
    domain_loaded_for_all_profiles = True
    
    # Check if the domain has data for all available profiles
    if len(domain_profiles) < len(available_profiles):
        continue
    
    # Check if all profiles have "loaded" status for this domain
    for profile in available_profiles:
        profile_status = df[(df['domain'] == domain) & (df['profile'] == profile)]['page_status'].values
        if len(profile_status) == 0 or profile_status[0] != 'loaded':
            domain_loaded_for_all_profiles = False
            break
    
    if domain_loaded_for_all_profiles:
        loaded_domains.add(domain)

print(f"Found {len(loaded_domains)} domains that loaded successfully for all profiles")

# Filter the dataframe to include only these domains
filtered_df = df[df['domain'].isin(loaded_domains)]

profile = 'adblock'
# List domains where adguard has "removed" status
adguard_removed_domains = filtered_df[(filtered_df['profile'] == profile) & 
                                    (filtered_df['banner_conclusion'] == 'removed')]['domain'].unique()
print(f"\nFound {len(adguard_removed_domains)} domains where {profile} has 'removed' banner status:")
for domain in adguard_removed_domains:
    print(f"  - {domain}")

# Calculate counts for each profile and banner conclusion
banner_counts = filtered_df.groupby(['profile', 'banner_conclusion']).size().unstack(fill_value=0)

# Remove "unknown" category from the results
if 'unknown' in banner_counts.columns:
    banner_counts = banner_counts.drop('unknown', axis=1)

# Create a new combined category for all removal-related conclusions
banner_counts['removed/likely removed'] = 0

# Add values from all removal-related categories
removal_categories = ['removed', 'likely removed', 'likely_removed']
for category in removal_categories:
    if category in banner_counts.columns:
        banner_counts['removed/likely removed'] += banner_counts[category]
        banner_counts = banner_counts.drop(category, axis=1)

# Reindex to ensure all profiles are included in the desired order
available_ordered_profiles = [p for p in ordered_profiles if p in banner_counts.index]
banner_counts = banner_counts.reindex(available_ordered_profiles)

# Define colors for the bars - adjusted to be more distinct
colors = {
    'not_removed': '#4682B4',      # Steel Blue - a stronger, more visible blue
    'removed/likely removed': '#98FB98'  # Pale Green - a softer but visible green
}

# Create a stacked bar chart
fig, ax = plt.subplots(figsize=(14, 8))
x = np.arange(len(banner_counts.index))

# Plot each banner conclusion as a stacked bar using our custom colors
bottom = np.zeros(len(banner_counts.index))
for i, conclusion in enumerate(banner_counts.columns):
    bars = ax.bar(x, banner_counts[conclusion], bottom=bottom, 
                 label=conclusion, color=colors[conclusion])
    
    # Add count labels inside the bars (only for bars with count > 1)
    for j, bar in enumerate(bars):
        height = bar.get_height()
        if height > 1:  # Only show label if bar has meaningful count
            ax.text(
                bar.get_x() + bar.get_width()/2., 
                bottom[j] + height/2,
                f"{int(height)}", 
                ha='center', va='center', 
                color='black', fontsize=8  # Changed text color to black for better visibility
            )
    
    bottom += banner_counts[conclusion].values

# Add labels and title
ax.set_ylabel('Number of Pages')
ax.set_title('Cookie Banners Removed per Browser Profile\n' + 
             '(For domains that loaded successfully across all profiles, English/Danish only)',
             loc='center', pad=20)  # loc='center' centers the title in the available space
ax.set_xticks(x)

# Use the imported display names for the x-tick labels
x_tick_labels = [DISPLAY_NAMES.get(profile, profile) for profile in banner_counts.index]
ax.set_xticklabels(x_tick_labels, rotation=45, ha='right')

# Set y-axis limit based on the data
y_max = banner_counts.sum(axis=1).max()
ax.set_ylim(0, y_max * 1.1)  # Add 10% margin above the highest bar

# Add a grid for better readability
ax.grid(axis='y', linestyle='--', alpha=0.3)

# Move legend to the top right, but more to the left
ax.legend(title='Banner Conclusion', 
         bbox_to_anchor=(0.98, 1.17),
         loc='upper right',
         ncol=1)  # Stack legend items vertically

# Determine the positions for the group dividers
group_dividers = []
current_position = 0

# Find the position after each group
for group_name, group_profiles in PROFILE_GROUPS.items():
    for profile in group_profiles:
        if profile in available_ordered_profiles:
            current_position += 1
    
    if current_position < len(available_ordered_profiles):
        group_dividers.append(current_position - 0.5)

# Add the vertical dotted lines to separate groups
for divider_pos in group_dividers:
    ax.axvline(x=divider_pos, color='black', linestyle=':', alpha=0.7)

# Add group labels above the bars
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_chart = [p for p in group_profiles if p in available_ordered_profiles]
    if group_profiles_in_chart:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_chart) - 1
        
        # Place the group label in the middle of the group
        label_position = (group_start + group_end) / 2
        
        # Add group label above the bars
        ax.text(
            label_position, y_max * 1.05,  # Position above the bars
            group_name, 
            ha='center', va='bottom', fontsize=10,
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.5)
        )
        
        current_position += len(group_profiles_in_chart)

# Adjust the layout to accommodate the legend
plt.subplots_adjust(top=0.85, right=0.85)  # Keep these margins the same

# Adjust the bottom margin since we removed the n-values
plt.subplots_adjust(bottom=0.2)  # Adjust this value as needed for x-tick label clarity

plt.tight_layout()
plt.savefig('banner_conclusion_by_profile_without_unknown.png', dpi=300, bbox_inches='tight')
plt.show() 