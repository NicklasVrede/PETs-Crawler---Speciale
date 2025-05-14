import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def plot_cookies_by_category_from_csv(csv_path):
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    # Remove rows with empty/missing primary_category
    df = df[df['primary_category'].notna() & (df['primary_category'] != '')]
    
    # Group by primary_category and sum the cookies
    category_data = df.groupby('primary_category').agg({
        'unique_cookies': 'sum',
        'potential_tracking_cookies_count': 'sum'
    }).reset_index()
    
    # Sort by total cookies (descending)
    category_data['total_cookies'] = category_data['unique_cookies']
    category_data = category_data.sort_values('total_cookies', ascending=False)
    
    # Calculate non-tracking cookies
    category_data['regular_cookies'] = category_data['unique_cookies'] - category_data['potential_tracking_cookies_count']
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get the data for plotting
    categories = category_data['primary_category']
    regular_cookies = category_data['regular_cookies']
    tracking_cookies = category_data['potential_tracking_cookies_count']
    
    # Plot stacked bars
    ax.bar(categories, regular_cookies, label='Regular Cookies', color='lightgray')
    ax.bar(categories, tracking_cookies, bottom=regular_cookies, label='Tracking Cookies', color='dimgray')
    
    # Add labels and title
    ax.set_xlabel('Website Category')
    ax.set_ylabel('Count of Cookies')
    ax.set_title('Cookie Distribution by Website Category')
    ax.legend()
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Save and show the plot
    plt.savefig('cookies_by_website_category.png')
    plt.show()

# Run the function with the path to your CSV file
plot_cookies_by_category_from_csv('data/csv/kameleo.csv') 