import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

# Set font sizes
plt.rcParams.update({
    'font.size': 14,
    'axes.labelsize': 16,
    'axes.titlesize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 14
})

# Get successful domains
def get_successful_domains():
    kameleo_df = pd.read_csv('data/csv/kameleo.csv')
    non_kameleo_df = pd.read_csv('data/csv/non-kameleo.csv')
    
    # Combine dataframes and find domains that loaded in both
    kameleo_loaded = set(kameleo_df[kameleo_df['page_status'] == 'loaded']['domain'])
    non_kameleo_loaded = set(non_kameleo_df[non_kameleo_df['page_status'] == 'loaded']['domain'])
    
    return kameleo_loaded.intersection(non_kameleo_loaded)

# Get successful domains
successful_domains = get_successful_domains()

# Read the CSV files
kameleo_df = pd.read_csv('data/csv/kameleo.csv')
non_kameleo_df = pd.read_csv('data/csv/non-kameleo.csv')

# Filter for successful domains
kameleo_successful = kameleo_df[kameleo_df['domain'].isin(successful_domains)]
non_kameleo_successful = non_kameleo_df[non_kameleo_df['domain'].isin(successful_domains)]

# Sum advertising domains
kameleo_sum = kameleo_successful['advertising_domains'].sum()
non_kameleo_sum = non_kameleo_successful['advertising_domains'].sum()

# Create the plot
plt.figure(figsize=(10, 6))

# Plot single bars
plt.bar(['kameleo', 'non-kameleo'], [kameleo_sum, non_kameleo_sum], 
        color=['#2ecc71', '#3498db'])

# Customize the plot
plt.xlabel('')
plt.ylabel('# advertising domains')

# Save the plot
plt.tight_layout()
plt.savefig('analysis/graphs/kameleo vs non-kameleo/advertising_domains_successful.png')
plt.close() 