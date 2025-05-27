import pandas as pd
import matplotlib.pyplot as plt

# Set font sizes
plt.rcParams.update({
    'font.size': 14,
    'axes.labelsize': 16,
    'axes.titlesize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 14
})

# Read the CSV files
kameleo_df = pd.read_csv('data/csv/kameleo.csv')
non_kameleo_df = pd.read_csv('data/csv/non-kameleo.csv')

# Count page_status for each dataset, excluding 'loaded'
kameleo_counts = kameleo_df[kameleo_df['page_status'] != 'loaded']['page_status'].value_counts()
non_kameleo_counts = non_kameleo_df[non_kameleo_df['page_status'] != 'loaded']['page_status'].value_counts()

# Create the plot
plt.figure(figsize=(10, 6))

# Plot bars with softer colors
x = range(len(kameleo_counts))
plt.bar([i - 0.2 for i in x], kameleo_counts.values, 0.4, label='kameleo', color='#2ecc71')
plt.bar([i + 0.2 for i in x], non_kameleo_counts.values, 0.4, label='non-kameleo', color='#3498db')

# Customize the plot
plt.xlabel('')
plt.ylabel('# pages')

# Set x-axis labels
plt.xticks(x, kameleo_counts.index)

# Add legend
plt.legend()

# Save the plot
plt.tight_layout()
plt.savefig('analysis/graphs/kameleo vs non-kameleo/page_status_errors.png')
plt.close() 