import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns  # Using seaborn for potentially better aesthetics and color palettes

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded'].copy() # Use .copy() to avoid SettingWithCopyWarning

# Ensure 'unique_cookies' is numeric, coercing errors to NaN
df_loaded['unique_cookies'] = pd.to_numeric(df_loaded['unique_cookies'], errors='coerce')

# Drop rows where 'unique_cookies' could not be converted (became NaN)
df_loaded.dropna(subset=['unique_cookies'], inplace=True)

# Convert 'unique_cookies' to integer type now that NaNs are handled
df_loaded['unique_cookies'] = df_loaded['unique_cookies'].astype(int)

# Get all unique profiles in a consistent order
all_profiles = sorted(df_loaded['profile'].unique())
print(f"Found {len(all_profiles)} unique profiles: {', '.join(all_profiles)}")

# Prepare data for boxplot: list of arrays/lists, one for each profile
boxplot_data = [df_loaded[df_loaded['profile'] == profile]['unique_cookies'].values for profile in all_profiles]

# Create readable labels and legend mapping
profile_labels_map = {}
legend_labels = []
for i, profile in enumerate(all_profiles):
    # Generate readable labels for legend
    if profile == 'no_extensions':
        readable_name = 'Baseline (No Extensions)' # More descriptive baseline
    elif profile == 'baseline_de':
         readable_name = 'Baseline (DE)'
    elif profile == 'baseline_us':
         readable_name = 'Baseline (USA)'
    else:
        # Format other profile names
        readable_name = ' '.join(word.capitalize() for word in profile.replace('_', ' ').split())

    label_num = f"#{i+1}"
    profile_labels_map[profile] = label_num
    legend_labels.append(f"{label_num}: {readable_name}")


# --- Plotting ---
plt.style.use('seaborn-v0_8-whitegrid') # Use a clean seaborn style
plt.figure(figsize=(12, 7))

# Create the boxplot
boxprops = dict(linestyle='-', linewidth=1.5, color='darkgrey')
medianprops = dict(linestyle='-', linewidth=2, color='black')
meanprops = dict(marker='.', markeredgecolor='black', markerfacecolor='black', markersize=10, linestyle=':') # Dotted line for mean
whiskerprops = dict(linestyle='-', linewidth=1.5, color='black')
capprops = dict(linestyle='-', linewidth=1.5, color='black')

bp = plt.boxplot(boxplot_data,
                 patch_artist=True, # Fill with color
                 showmeans=True,    # Show means
                 meanline=False,    # Show mean as marker, not line across box
                 meanprops=meanprops,
                 medianprops=medianprops,
                 boxprops=boxprops,
                 whiskerprops=whiskerprops,
                 capprops=capprops,
                 showfliers=False) # Hide outliers for cleaner look like example

# Set box colors (e.g., light grey)
for patch in bp['boxes']:
    patch.set_facecolor('lightgrey')
    patch.set_edgecolor('grey')

# Customize the plot
plt.title('Distribution of Unique Cookies per Profile', fontsize=16, pad=20)
plt.ylabel('Number of cookies', fontsize=14)
plt.xlabel('Profile', fontsize=14)

# Set x-axis ticks and labels using the numeric mapping
x_ticks = np.arange(1, len(all_profiles) + 1)
x_tick_labels = [profile_labels_map[profile] for profile in all_profiles]
plt.xticks(x_ticks, x_tick_labels)

# Add the legend explaining the numbered profiles
# Place legend similarly to the example image
plt.legend(handles=[plt.plot([], [], ' ', label=lbl)[0] for lbl in legend_labels], # Create dummy handles for text legend
           title="Profiles",
           loc='upper right',
           bbox_to_anchor=(1.0, 1.0), # Adjust as needed
           ncol=3, # Arrange legend in columns
           handlelength=0, handletextpad=0, # Hide dummy handle markers
           labelspacing=0.5)


# Adjust y-axis limits if needed, ensure it starts at 0
max_whisker = max([max(item.get_ydata()) for item in bp['whiskers']])
plt.ylim(bottom=-5, top=max_whisker * 1.1) # Start slightly below 0, extend slightly above max whisker

plt.tight_layout(rect=[0, 0, 1, 0.95]) # Adjust layout to prevent title overlap
plt.savefig('unique_cookie_count_boxplot.png', dpi=300, bbox_inches='tight')
plt.show()

print("\nBoxplot saved as unique_cookie_count_boxplot.png") 