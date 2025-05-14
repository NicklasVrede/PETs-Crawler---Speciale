import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Focus on the cookie-related extensions
target_extensions = ['consent_o_matic_opt_in', 'consent_o_matic_opt_out', 'accept_all_cookies']
profiles_to_analyze = target_extensions + ['no_extensions']

# Find domains that loaded successfully with all target profiles
domains_with_successful_loads = set()
for profile in profiles_to_analyze:
    profile_domains = set(df_loaded[df_loaded['profile'] == profile]['domain'].unique())
    if not domains_with_successful_loads:
        domains_with_successful_loads = profile_domains
    else:
        domains_with_successful_loads = domains_with_successful_loads.intersection(profile_domains)

print(f"Analyzing {len(domains_with_successful_loads)} domains that loaded successfully for all target profiles")

# Filter the dataset to only include those domains and our target profiles
df_analysis = df_loaded[
    (df_loaded['domain'].isin(domains_with_successful_loads)) & 
    (df_loaded['profile'].isin(profiles_to_analyze))
]

# Filter for cases where banners were successfully removed by all target extensions
banner_removed_domains = {}
for ext in target_extensions:
    # Get domains where this extension successfully removed the banner
    successful_domains = df_analysis[
        (df_analysis['profile'] == ext) & 
        (df_analysis['banner_conclusion'].isin(['removed', 'likely removed', 'likely_removed']))
    ]['domain'].unique()
    
    banner_removed_domains[ext] = set(successful_domains)
    print(f"{ext}: Successfully removed banners on {len(successful_domains)} domains")

# Find domains where all extensions successfully removed banners
common_success_domains = set.intersection(*[banner_removed_domains[ext] for ext in target_extensions])
print(f"All extensions successfully removed banners on {len(common_success_domains)} domains")

# Create a dataset focusing only on successful banner removals
df_success = df_analysis[
    (df_analysis['domain'].isin(common_success_domains)) & 
    (df_analysis['profile'].isin(target_extensions + ['no_extensions']))
]

# Define only purpose-based cookie categories to analyze (excluding unclassified_cookies)
cookie_categories = [
    'necessary_cookies',
    'preference_cookies',
    'functional_cookies',
    'marketing_cookies',
    'statistics_cookies'
]

# Check which categories are actually in the dataset
available_categories = [col for col in cookie_categories if col in df_success.columns]
if len(available_categories) < len(cookie_categories):
    missing = set(cookie_categories) - set(available_categories)
    print(f"Warning: The following cookie categories are not in the dataset: {', '.join(missing)}")
    cookie_categories = available_categories

# Create a DataFrame with the mean values for each profile and category
means_data = []
profiles = ['no_extensions'] + target_extensions

for profile in profiles:
    profile_data = df_success[df_success['profile'] == profile]
    for category in cookie_categories:
        if category in profile_data.columns:
            means_data.append({
                'profile': profile,
                'category': category,
                'mean': profile_data[category].mean()
            })

means_df = pd.DataFrame(means_data)

# Create readable labels for x-axis
profile_labels = {
    'no_extensions': 'No Extensions',
    'consent_o_matic_opt_in': 'Consent-O-Matic\n(Accept All)',
    'consent_o_matic_opt_out': 'Consent-O-Matic\n(Reject All)',
    'accept_all_cookies': 'Accept All\nCookies'
}

# Create the grouped bar chart
plt.figure(figsize=(14, 8))

# Set up the bar positions
x = np.arange(len(profiles))
bar_width = 0.8 / len(cookie_categories)
total_width = bar_width * len(cookie_categories)

# Create a color palette - use a colorblind-friendly palette
colors = sns.color_palette("colorblind", len(cookie_categories))

# Plot each category as a group of bars
for i, category in enumerate(cookie_categories):
    category_data = means_df[means_df['category'] == category]
    category_means = [category_data[category_data['profile'] == profile]['mean'].values[0] 
                    if not category_data[category_data['profile'] == profile].empty 
                    else 0 for profile in profiles]
    
    # Calculate position for this group of bars
    pos = x - total_width/2 + i * bar_width + bar_width/2
    
    bars = plt.bar(pos, category_means, width=bar_width, label=category.replace('_', ' ').title(), color=colors[i], alpha=0.8)
    
    # Add value labels on top of each bar
    for j, bar in enumerate(bars):
        height = bar.get_height()
        if height > 0:  # Only add labels for non-zero values
            plt.text(bar.get_x() + bar.get_width()/2, height + 0.3,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9, rotation=0)

# Customize the plot
plt.title('Cookie Purpose Categories Comparison Across Extensions', fontsize=16, pad=20)
plt.ylabel('Average Count', fontsize=14)
plt.xlabel('Browser Profile', fontsize=14)
plt.grid(axis='y', linestyle='--', alpha=0.3)
plt.xticks(x, [profile_labels[profile] for profile in profiles])

# Create a more readable legend
plt.legend(title='Cookie Category', bbox_to_anchor=(1.05, 1), loc='upper left')

# Ensure y-axis starts at 0
plt.ylim(bottom=0)

plt.tight_layout()
plt.savefig('cookie_purpose_categories_comparison.png', dpi=300, bbox_inches='tight')
plt.show()

# --- Removed Heatmap and Reduction Code ---
# (Code for heatmap and reduction analysis remains removed)


# --- Generate Plots for 5 Random Domains ---
print("\n--- Generating Plots for 5 Random Domains ---")
output_dir_domains = "analysis_output/domain_specific_plots"
os.makedirs(output_dir_domains, exist_ok=True)

# Ensure we have enough domains to sample from
num_domains_to_plot = 5
available_domains = list(common_success_domains) # Use domains where all extensions worked

if len(available_domains) >= num_domains_to_plot:
    # Randomly select 5 domains
    import random
    selected_domains = random.sample(available_domains, num_domains_to_plot)
    print(f"Selected domains for plotting: {', '.join(selected_domains)}")

    # Define profiles and categories again for plotting
    profiles_to_plot = ['no_extensions'] + target_extensions
    profile_labels_plot = { # Use the same labels as before
        'no_extensions': 'No Ext',
        'consent_o_matic_opt_in': 'CoM\n(Accept)',
        'consent_o_matic_opt_out': 'CoM\n(Reject)',
        'accept_all_cookies': 'Accept All'
    }
    # Use the cookie categories defined earlier
    # cookie_categories = ['necessary_cookies', 'preference_cookies', ...]

    for domain in selected_domains:
        plt.figure(figsize=(10, 7))
        domain_data = df_success[df_success['domain'] == domain]

        plot_data = []
        for profile in profiles_to_plot:
            profile_domain_data = domain_data[domain_data['profile'] == profile]
            # Ensure there's data for this profile/domain combo
            if not profile_domain_data.empty:
                row = profile_domain_data.iloc[0] # Get the single row for this combo
                for category in cookie_categories:
                    if category in row:
                        plot_data.append({
                            'profile': profile,
                            'category': category,
                            'count': row[category]
                        })
            else: # Add zeros if no data found (shouldn't happen with common_success_domains)
                 for category in cookie_categories:
                     plot_data.append({'profile': profile, 'category': category, 'count': 0})


        plot_df = pd.DataFrame(plot_data)

        # Create the grouped bar chart for this domain
        x = np.arange(len(profiles_to_plot))
        num_categories = len(cookie_categories)
        bar_width = 0.8 / num_categories
        total_width = bar_width * num_categories
        colors = sns.color_palette("colorblind", num_categories)

        for i, category in enumerate(cookie_categories):
            category_counts = plot_df[plot_df['category'] == category]['count'].values
            pos = x - total_width/2 + i * bar_width + bar_width/2
            bars = plt.bar(pos, category_counts, width=bar_width, label=category.replace('_', ' ').title(), color=colors[i], alpha=0.8)
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    plt.text(bar.get_x() + bar.get_width()/2, height + 0.1, f'{int(height)}', ha='center', va='bottom', fontsize=8)


        plt.title(f'Cookie Categories for {domain}', fontsize=14, pad=15)
        plt.ylabel('Count', fontsize=12)
        plt.xlabel('Browser Profile', fontsize=12)
        plt.xticks(x, [profile_labels_plot[p] for p in profiles_to_plot], fontsize=10)
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.legend(title='Cookie Category', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
        plt.ylim(bottom=0)
        plt.tight_layout(rect=[0, 0, 0.85, 1]) # Adjust layout to make space for legend

        # Sanitize domain name for filename
        safe_domain_name = "".join([c if c.isalnum() else "_" for c in domain])
        filename = f'domain_{safe_domain_name}_cookie_comparison.png'
        filepath = os.path.join(output_dir_domains, filename)
        plt.savefig(filepath, dpi=300)
        plt.close()
        print(f"Plot saved: {filepath}")

else:
    print(f"Not enough common success domains ({len(available_domains)}) to plot {num_domains_to_plot}.")


# --- Domain Analysis (Previous code removed/commented) ---
# print("\n--- Domain Analysis ---")
# ... (The incorrect code based on session_duration/session_id is removed) ...

# --- Plotting (Previous code removed/commented) ---
# print("\n--- Generating Plots ---")
# ... (The incorrect code based on session_duration/session_id is removed) ...


print("\n--- Analysis Complete ---")
# Modify the final message if needed, e.g., point to the new directory
print(f"Comparison plot saved as cookie_purpose_categories_comparison.png")
print(f"Domain-specific plots saved in: {output_dir_domains}") 