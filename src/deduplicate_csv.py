import pandas as pd

# Read the CSV file
df = pd.read_csv("data/csv/final_data.csv")

# Check for duplicate domain entries per profile before deduplication
duplicate_check = df.groupby(['profile', 'domain']).size().reset_index(name='count')
duplicates = duplicate_check[duplicate_check['count'] > 1]
pd.set_option('display.max_rows', None)  # Show all rows
print("Duplicate entries found:")
print(duplicates)

# Remove duplicates, keeping the first occurrence
df_deduplicated = df.drop_duplicates(subset=['profile', 'domain'], keep='first')

# Save the deduplicated data
df_deduplicated.to_csv("data/csv/final_data_deduplicated.csv", index=False)

print(f"\nOriginal number of rows: {len(df)}")
print(f"Number of rows after deduplication: {len(df_deduplicated)}") 