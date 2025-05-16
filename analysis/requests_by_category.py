import pandas as pd, matplotlib.pyplot as plt
import numpy as np
import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Use all request columns
simplified_cols = [
    "social_media_requests",        # Social Media
    "advertising_requests",         # Advertising
    "analytics_requests",          # Analytics
    "consent_management_requests",  # Consent Management
    "hosting_requests",            # Hosting
    "customer_interaction_requests", # Customer Interaction
    "audio_video_requests",        # Audio/Video
    "extensions_requests",         # Extensions
    "adult_advertising_requests",  # Adult Advertising
    "utilities_requests",          # Utilities
    "miscellaneous_requests",      # Miscellaneous
    "uncategorized_requests"       # Uncategorized
]

# Colors for each category (we'll need to add more colors)
simplified_colors = [
    "#ff0000",  # Social Media - bright red
    "#ff9999",  # Advertising - light red/pink
    "#008800",  # Analytics - green
    "#ccff99",  # Consent Management - light green
    "#0066cc",  # Hosting - blue
    "#99ccff",  # Customer Interaction - light blue
    "#ff00ff",  # Audio/Video - magenta
    "#ffcc00",  # Extensions - yellow
    "#ff6600",  # Adult Advertising - orange
    "#666666",  # Utilities - gray
    "#000000",  # Miscellaneous - black
    "#cccccc",  # Uncategorized - light gray
]

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
df = df_loaded[df_loaded['domain'].isin(successful_domains)]

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure we only use profiles that exist in our data
all_profiles = [p for p in ordered_profiles if p in df['profile'].unique()]

# Calculate total requests per profile
profile_totals = df.groupby("profile")["total_requests"].sum()

# Find no_extensions total
no_extensions_total = profile_totals.get("no_extensions", 1)  # Default to 1 if not found
print(f"No extensions total: {no_extensions_total}")

# Calculate scaling factor for each profile relative to no_extensions
scaling_factors = profile_totals / no_extensions_total
print("Scaling factors:")
print(scaling_factors)

# Find maximum scaling factor for setting y-axis limit
max_scaling = scaling_factors.max()
y_limit = max(110, max_scaling * 105)  # At least 110% or 5% above the maximum
print(f"Maximum scaling: {max_scaling}, Y-axis limit: {y_limit}")

# Calculate request type counts for each profile
g = df.groupby("profile")[simplified_cols].sum()

# Reindex to get the desired order
g = g.reindex(all_profiles)

# Calculate percentages within each profile
share = g.div(g.sum(axis=1), axis=0) * 100

# Scale the percentages by the total requests ratio
scaled_share = share.copy()
for profile in scaled_share.index:
    if profile in scaling_factors:
        scaled_share.loc[profile] = share.loc[profile] * scaling_factors[profile]

fig, ax = plt.subplots(figsize=(14, 6))
scaled_share.plot(kind="bar", stacked=True,
           color=simplified_colors,
           ax=ax)

# Add group labels above the plot
y_max = scaled_share.sum(axis=1).max()
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.10, group_name,
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

# Update legend labels
handles, old_labels = ax.get_legend_handles_labels()
legend_labels = [col.replace('_requests', '') for col in simplified_cols]

# Special cases for multi-word labels
special_cases = {
    "social_media": "Social Media",
    "consent_management": "Consent Management",
    "customer_interaction": "Customer Interaction",
    "audio_video": "Audio/Video",
    "adult_advertising": "Adult Advertising"
}

# Update labels
for i, label in enumerate(legend_labels):
    if label in special_cases:
        legend_labels[i] = special_cases[label]
    else:
        legend_labels[i] = label.title()

ax.legend(handles, legend_labels, bbox_to_anchor=(1.05, 1), loc='upper left')

# Updated y-axis label to clarify that it includes all requests (both first-party and third-party)
ax.set_ylabel("All requests by category relative to baseline (100%)")
ax.set_ylim(0, y_limit)  # Set dynamic limit based on data

# Add a horizontal line at 100% for reference
ax.axhline(y=100, color='black', linestyle='-', alpha=0.5, linewidth=1)

# Add grid lines
plt.grid(axis='y', linestyle='-', alpha=0.2)

# Add a text annotation for bars exceeding 100%
for i, profile in enumerate(scaled_share.index):
    total = scaled_share.loc[profile].sum()
    if total > 100:
        plt.text(i, 100, f"{total:.0f}%", ha='center', va='bottom', fontsize=8, rotation=0)

# Use display names for x-tick labels
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
          rotation=45, ha="right")

plt.tight_layout()
plt.show()
