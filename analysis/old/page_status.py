import pandas as pd

# Load the CSV files
kameleo = pd.read_csv("data/csv/kameleo.csv")
non_kameleo = pd.read_csv("data/csv/non-kameleo.csv")

# Extract the 'domain' and 'page_status' columns
kameleo_status = kameleo[["domain", "page_status"]].copy()
non_kameleo_status = non_kameleo[["domain", "page_status"]].copy()

# Merge the two datasets on domain
status_merged = pd.merge(
    kameleo_status,
    non_kameleo_status,
    on="domain",
    suffixes=("_kameleo", "_non_kameleo"),
    how="inner"
)

# Filter to get only domains where the page_status changed
status_changed_domains = status_merged[
    status_merged["page_status_kameleo"] != status_merged["page_status_non_kameleo"]
].copy()

# Remove duplicate rows for the same domain with the same status values
status_changed_domains = status_changed_domains.drop_duplicates()

# Count unique domains with status changes
print(f"Total unique domains with status changes: {status_changed_domains['domain'].nunique()}")

# Display result
print(status_changed_domains)
