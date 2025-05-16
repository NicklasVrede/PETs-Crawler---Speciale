import os
import json
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from collections import defaultdict, Counter

def validate_json_file(file_path):
    """
    Validate if a file contains valid JSON.
    Deletes files that are too short (likely empty or just 'null').
    Returns (file_path, folder, filename, is_valid, error_message)
    """
    folder = os.path.basename(os.path.dirname(file_path))
    filename = os.path.basename(file_path)
    
    try:
        # First check file size/content
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) < 10:  # If file has fewer than 10 lines
                try:
                    os.remove(file_path)
                    print(f"[ACTION] Deleted short file ({len(lines)} lines): {file_path}")
                    return file_path, folder, filename, False, f"Deleted (too short: {len(lines)} lines)"
                except OSError as delete_error:
                    return file_path, folder, filename, False, f"File too short but deletion failed: {str(delete_error)}"
        
        # If file is long enough, validate JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return file_path, folder, filename, True, None

    except json.JSONDecodeError as e:
        original_error_str = str(e)
        # Check for "Invalid control character" errors first
        if "Invalid control character" in original_error_str:
            # Optionally, print details about the invalid character before attempting deletion
            file_content_for_debug = ""
            try:
                with open(file_path, 'r', encoding='utf-8') as f_debug_read: # Read again for debug, file might be large
                    file_content_for_debug = f_debug_read.read()
                if 0 <= e.pos < len(file_content_for_debug):
                    invalid_char = file_content_for_debug[e.pos]
                    print(f"\n[INFO] File: {file_path} contains invalid control character: {repr(invalid_char)} (U+{ord(invalid_char):04X}) at pos {e.pos}. Error: {original_error_str}")
                else:
                    print(f"\n[INFO] File: {file_path} contains invalid control character. Error: {original_error_str}. Position {e.pos} out of bounds for len {len(file_content_for_debug)}.")
            except Exception as debug_read_error:
                print(f"\n[INFO] File: {file_path} contains invalid control character. Error: {original_error_str}. Could not read file to show char: {debug_read_error}")

            # Attempt to delete the file
            try:
                os.remove(file_path)
                print(f"[ACTION] Deleted file: {file_path} due to invalid control character.")
                return file_path, folder, filename, False, f"Deleted (invalid control character: {original_error_str})"
            except OSError as delete_error:
                print(f"[ERROR] Failed to delete file {file_path} which has invalid control character. Error: {delete_error}")
                return file_path, folder, filename, False, f"JSON decode error (invalid control char): {original_error_str}. Deletion attempt failed: {delete_error}"
        
        # If not an "Invalid control character" error, or if deletion failed, proceed to 'null' check
        try:
            with open(file_path, 'r', encoding='utf-8') as f_read:
                content = f_read.read().strip()
            
            if content == 'null':
                print(f"[INFO] Found null-only file: {file_path}")
                try:
                    os.remove(file_path)
                    print(f"[ACTION] Deleted null-only file: {file_path}")
                    return file_path, folder, filename, False, "Deleted (contained only 'null')"
                except OSError as delete_error:
                    print(f"[ERROR] Failed to delete null-only file {file_path}. Error: {delete_error}")
                    return file_path, folder, filename, False, f"Contains only 'null'. Deletion attempt failed: {delete_error}"
            else:
                # If not 'null', return original error
                return file_path, folder, filename, False, f"JSON decode error: {original_error_str}"
        except Exception as repair_exception:
            # If repair attempt itself causes an error, return original decode error plus repair error
            return file_path, folder, filename, False, f"JSON decode error: {original_error_str}. Repair attempt failed: {str(repair_exception)}"
    except Exception as e:
        return file_path, folder, filename, False, f"Error reading file: {str(e)}"

def delete_invalid_files(invalid_files):
    """Delete invalid JSON files"""
    deleted_count = 0
    failed_count = 0
    
    print("\nDeleting invalid JSON files...")
    for file_path, error in invalid_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[DELETED] {file_path}")
                deleted_count += 1
            else:
                print(f"[WARNING] File already deleted: {file_path}")
        except Exception as e:
            print(f"[ERROR] Failed to delete {file_path}: {str(e)}")
            failed_count += 1
    
    print(f"\nDeletion summary: {deleted_count} files deleted, {failed_count} deletion failures")
    return deleted_count, failed_count

def check_json_files(base_dir, max_workers=None):
    """Check all JSON files in the crawler data directories for validity"""
    
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return

    # Get all folders in the base directory
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        print("No folders found")
        return

    # Collect all JSON files and track filenames by folder
    all_files = []
    files_per_folder = {}
    all_filenames = []
    
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        files_per_folder[folder] = set(json_files)
        all_filenames.extend(json_files)
        all_files.extend([os.path.join(folder_path, f) for f in json_files])

    # Analyze filename consistency
    filename_counts = Counter(all_filenames)
    expected_count = len(folders)  # Each file should appear in every folder
    
    inconsistent_files = {
        filename: count for filename, count in filename_counts.items()
        if count != expected_count
    }

    # Find unique files per folder
    unique_files = defaultdict(list)
    for folder, files in files_per_folder.items():
        for filename in files:
            if filename_counts[filename] != expected_count:
                unique_files[folder].append(filename)

    total_files = len(all_files)
    if not total_files:
        print("No JSON files found")
        return

    # Use maximum number of workers or CPU count
    if max_workers is None:
        max_workers = cpu_count()

    # Process files in parallel
    files_by_folder = defaultdict(list)
    invalid_files = []
    
    print(f"\nValidating {total_files} files using {max_workers} processes...")
    
    with Pool(processes=max_workers) as pool:
        for result in tqdm(
            pool.imap_unordered(validate_json_file, all_files),
            total=total_files,
            desc="Checking files"
        ):
            file_path, folder, filename, is_valid, error = result
            if not is_valid:
                files_by_folder[folder].append((filename, error))
                invalid_files.append((file_path, error))

    # Print results
    print("\nValidation Results:")
    print(f"Total files checked: {total_files}")
    print(f"Invalid files found: {len(invalid_files)}")
    
    # Print consistency analysis
    print("\nFile Consistency Analysis:")
    print(f"Number of folders: {len(folders)}")
    print(f"Files with unexpected occurrence count: {len(inconsistent_files)}")
    
    if inconsistent_files:
        print("\nInconsistent files (showing count per file):")
        for filename, count in sorted(inconsistent_files.items()):
            print(f"- {filename}: found in {count} folders (expected in {expected_count})")
        
        print("\nBreakdown by folder:")
        for folder, files in sorted(unique_files.items()):
            if files:
                print(f"\nFolder: {folder}")
                print("=" * (8 + len(folder)))
                for filename in sorted(files):
                    count = filename_counts[filename]
                    print(f"- {filename} (found in {count} folders)")
    
    if invalid_files:
        print("\nList of invalid files by folder:")
        for folder in sorted(files_by_folder.keys()):
            print(f"\nFolder: {folder}")
            print("=" * (8 + len(folder)))
            for filename, error in sorted(files_by_folder[folder]):
                print(f"\nFile: {filename}")
                print(f"Error: {error}")
        
        # Always delete invalid files
        delete_invalid_files(invalid_files)

if __name__ == "__main__":
    check_json_files("data/crawler_data", max_workers=None)  # None means use all available CPU cores 