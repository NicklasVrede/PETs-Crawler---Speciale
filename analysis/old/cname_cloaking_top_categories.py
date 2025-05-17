import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read the CSV data
df = pd.read_csv("data/csv/non-kameleo.csv")

# Function to process both primary and additional categories
def get_all_categories(row):
    categories = []
    # Add primary category if it exists, otherwise add "No Category"
    if pd.notna(row['primary_category']) and row['primary_category']:
        categories.append(row['primary_category'])
    else:
        categories.append("No Category")
    
    # Add additional categories if they exist
    if pd.notna(row['additional_categories']) and row['additional_categories']:
        additional = row['additional_categories'].split(',')
        categories.extend([cat.strip() for cat in additional])
    return categories

# Create a new dataframe with expanded categories
expanded_categories = []
for _, row in df.iterrows():
    for category in get_all_categories(row):
        if category:  # Ensure the category is not empty
            expanded_categories.append({
                'category': category,
                'potential_cname_cloaking': row['potential_cname_cloaking']
            })

expanded_df = pd.DataFrame(expanded_categories)

# Group by category and sum the potential CNAME cloaking counts
cname_by_category = expanded_df.groupby('category')['potential_cname_cloaking'].sum().reset_index()

# Sort from highest to lowest count
cname_by_category = cname_by_category.sort_values('potential_cname_cloaking', ascending=False)

# Keep only the top 15 categories
top_categories = cname_by_category.head(15)

# Create the visualization
plt.figure(figsize=(12, 8))
plt.bar(top_categories['category'], top_categories['potential_cname_cloaking'], color='black')

# Add labels and title
plt.xlabel('Category', fontsize=14)
plt.ylabel('Number of cloaked CNAMEs (eTLD+1)', fontsize=14)
plt.xticks(rotation=45, ha='right', fontsize=12)
plt.yticks(fontsize=12)

# Add grid lines for y-axis only
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the figure
plt.savefig('cname_cloaking_top_categories.png', dpi=300)

# Show the plot
plt.show()

# Print the data for reference
print(top_categories) 