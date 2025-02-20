import csv

def filter_dk_domains(input_file, output_file):
    dk_sites = []
    
    print("Reading CSV file...")
    with open(input_file, 'r') as f:
        reader = csv.reader(f)
        for rank, domain in reader:
            if domain.endswith('.dk'):
                dk_sites.append((rank, domain))
    
    print(f"Found {len(dk_sites)} .dk domains")
    
    print("Writing to output file...")
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(dk_sites)
    
    print("Done!")
    print("\nFirst 10 .dk sites found:")
    for rank, domain in dk_sites[:10]:
        print(f"{rank}. {domain}")

if __name__ == "__main__":
    filter_dk_domains('data/top-1m.csv', 'data/dk-domains.csv') 