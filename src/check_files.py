import os



def print_files(path, level=0):
    try:
        # Print current directory
        print("  " * level + f"Directory: {path}")
        
        # List contents
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                print_files(item_path, level + 1)
            else:
                print("  " * (level + 1) + f"File: {item}")
    except Exception as e:
        print(f"Error reading {path}: {str(e)}")

# Check the trackerdb directory
print_files('data/databases/trackerdb-main') 