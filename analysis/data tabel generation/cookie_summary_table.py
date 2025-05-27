import os
import sys
import pandas as pd
import numpy as np

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Group by profile and calculate sums/means
summary = df_loaded.groupby('profile').agg({
    'unique_cookies': 'sum',
    'first_party_cookies': 'sum',
    'third_party_cookies': 'sum',
    'necessary_cookies': 'sum',
    'functional_cookies': 'sum',
    'performance_cookies': 'sum',
    'advertising_cookies': 'sum',
    'analytics_cookies': 'sum',
    'other_cookies': 'sum',
    'unknown_cookies': 'sum',
    'shared_identifiers_count': 'sum',  # 1P Tracking Cookies
    'local_storage_count': 'sum',
    'session_storage_count': 'sum'
}).round(0).astype(int)

# Add Others/Unknown column (combining other_cookies and unknown_cookies)
summary['others_and_unknown'] = summary['other_cookies'] + summary['unknown_cookies']

# Reorder columns
columns = [
    'unique_cookies',
    'first_party_cookies',
    'third_party_cookies',
    'necessary_cookies',
    'functional_cookies',
    'performance_cookies',
    'advertising_cookies',
    'analytics_cookies',
    'others_and_unknown',
    'shared_identifiers_count',
    'local_storage_count',
    'session_storage_count'
]

# Create final table with display names
summary = summary[columns]
summary.index = summary.index.map(lambda x: DISPLAY_NAMES.get(x, x))

# Rename columns for better readability
column_names = {
    'unique_cookies': 'Total Cookies',
    'first_party_cookies': '1P Cookies',
    'third_party_cookies': '3P Cookies',
    'necessary_cookies': 'Necessary',
    'functional_cookies': 'Functional',
    'performance_cookies': 'Performance',
    'advertising_cookies': 'Advertising',
    'analytics_cookies': 'Analytics',
    'others_and_unknown': 'Others/Unknown',
    'shared_identifiers_count': '1P Tracking Cookies',
    'local_storage_count': 'LocalStorage',
    'session_storage_count': 'SessionStorage'
}
summary.columns = [column_names[col] for col in columns]

# Sort profiles by groups
ordered_profiles = []
for group in PROFILE_GROUPS.values():
    for profile in group:
        if DISPLAY_NAMES.get(profile) in summary.index:
            ordered_profiles.append(DISPLAY_NAMES.get(profile))
summary = summary.reindex(ordered_profiles)

# Print the table
print("\nCookie and Storage-Based Tracking Summary")
print("=" * 100)
print(summary.to_string())

# Save to CSV
summary.to_csv('analysis/data tabel generation/cookie_summary_table.csv')

# Calculate and print some additional statistics
print("\nAdditional Statistics:")
print("=" * 100)

baseline = summary.loc[DISPLAY_NAMES['no_extensions']]
print(f"\nBaseline Profile ({DISPLAY_NAMES['no_extensions']}):")
for col in summary.columns:
    print(f"{col}: {baseline[col]:,}")

print("\nAverage reduction compared to baseline:")
for idx in summary.index:
    if idx != DISPLAY_NAMES['no_extensions']:
        reduction = (baseline - summary.loc[idx]) / baseline * 100
        print(f"\n{idx}:")
        for col in summary.columns:
            print(f"{col}: {reduction[col]:.1f}%") 