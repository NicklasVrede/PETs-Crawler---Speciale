# Re-import necessary packages after kernel reset
import pandas as pd

# Reload uploaded files
kameleo = pd.read_csv("data/csv/kameleo.csv")
non_kameleo = pd.read_csv("data/csv/non-kameleo.csv")

# Filter relevant columns
kameleo_subset = kameleo[["domain", "page_loaded"]].copy()
kameleo_subset["source"] = "kameleo"

non_kameleo_subset = non_kameleo[["domain", "page_loaded"]].copy()
non_kameleo_subset["source"] = "non-kameleo"

# Merge on domain
merged = pd.merge(
    kameleo_subset,
    non_kameleo_subset,
    on="domain",
    suffixes=("_kameleo", "_non_kameleo"),
    how="inner"
)

# Filter: True in kameleo, False in non-kameleo
only_kameleo_loaded = merged[
    (merged["page_loaded_kameleo"] == True) &
    (merged["page_loaded_non_kameleo"] == False)
]

# Print only the unique domains
print(only_kameleo_loaded["domain"].unique())
