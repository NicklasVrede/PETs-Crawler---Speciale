import os
import shutil
import filecmp
from pathlib import Path
import datetime

def get_dir_size(path):
    """Calculate the total size of a directory in bytes"""
    total_size = 0
    path = Path(path)
    
    for item in path.glob('**/*'):
        if item.is_file():
            total_size += item.stat().st_size
    
    return total_size

def format_size(size_bytes):
    """Format size in bytes to human-readable format"""
    # Define size units
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    
    # Determine the appropriate unit
    unit_index = 0
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1
    
    # Return formatted string with up to 2 decimal places
    return f"{size_bytes:.2f} {units[unit_index]}"

def get_unique_items(source_dir, reference_dir, verbose=False):
    """Find files and directories in source_dir that don't exist in reference_dir"""
    source_path = Path(source_dir)
    reference_path = Path(reference_dir)
    
    unique_items = []
    
    # Iterate through all items in the source directory
    for item in source_path.glob('**/*'):
        # Get the relative path to compare with reference
        rel_path = item.relative_to(source_path)
        reference_item = reference_path / rel_path
        
        # If item is a file and doesn't exist in reference, or content is different
        if item.is_file():
            if not reference_item.exists():
                unique_items.append(rel_path)
                if verbose:
                    print(f"Unique file: {rel_path}")
        
        # If item is a directory that doesn't exist in reference
        elif item.is_dir() and not reference_item.exists():
            # We only need to add the top level directory
            if not any(str(rel_path).startswith(str(existing)) for existing in unique_items):
                unique_items.append(rel_path)
                if verbose:
                    print(f"Unique directory: {rel_path}")
    
    return unique_items

def clean_profiles(profiles_root, base_profile="no_extensions", dry_run=False, verbose=True):
    """
    Clean all profiles using a smarter approach that preserves only unique files.
    Reports size before and after cleaning.
    
    Args:
        profiles_root: Root directory containing all profiles
        base_profile: Name of the clean profile to use as a base
        dry_run: If True, only print actions without executing them
        verbose: If True, print detailed information
    """
    # Convert to Path object for easier manipulation
    profiles_root = Path(profiles_root)
    base_profile_path = profiles_root / base_profile
    
    # Check if base profile exists
    if not base_profile_path.exists():
        print(f"Error: Base profile '{base_profile}' not found in {profiles_root}")
        return
    
    if verbose:
        print(f"Using {base_profile_path} as the clean reference profile")
    
    # Get all profile directories except the base profile
    profiles_to_clean = [d for d in profiles_root.iterdir() 
                        if d.is_dir() and d.name != base_profile]
    
    if verbose:
        print(f"Found {len(profiles_to_clean)} profiles to clean")
        
    # Track total size savings
    total_size_before = 0
    total_size_after = 0
    
    # Process each profile
    for profile_path in profiles_to_clean:
        profile_name = profile_path.name
        print(f"\nProcessing profile: {profile_name}")
        
        # Calculate initial size
        initial_size = get_dir_size(profile_path)
        total_size_before += initial_size
        print(f"  Initial size: {format_size(initial_size)}")
        
        # Get unique items in this profile compared to base profile
        if verbose:
            print(f"  Finding unique files and directories in {profile_name}...")
        
        unique_items = get_unique_items(profile_path, base_profile_path, verbose=False)
        
        if not unique_items:
            print(f"  No unique items found in {profile_name}, skipping...")
            continue
            
        print(f"  Found {len(unique_items)} unique items to preserve")
        
        # Create temporary storage for unique files in data/temp_profiles
        temp_dir = temp_profiles_dir / profile_name
        if not dry_run:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)
        
        # Back up unique files
        if verbose:
            print(f"  Backing up unique items to {temp_dir}...")
            
        if not dry_run:
            for rel_path in unique_items:
                source_path = profile_path / rel_path
                target_path = temp_dir / rel_path
                
                # Create parent directories if needed
                if not target_path.parent.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy directory or file
                if source_path.is_dir():
                    shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, target_path)
        
        # Clear the profile directory
        if verbose:
            print(f"  Clearing profile: {profile_name}")
        
        if not dry_run:
            # Remove all contents except Cache and Code Cache
            for item in profile_path.iterdir():
                if item.name != "Cache" and item.name != "Code Cache":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        
        # Copy base profile contents
        if verbose:
            print(f"  Copying clean profile from: {base_profile}")
        
        if not dry_run:
            for item in base_profile_path.iterdir():
                target = profile_path / item.name
                
                # Skip if target already exists (like Cache)
                if target.exists():
                    continue
                    
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
        
        # Restore unique files
        if verbose:
            print(f"  Restoring unique items from {temp_dir}...")
            
        if not dry_run:
            for rel_path in unique_items:
                source_path = temp_dir / rel_path
                target_path = profile_path / rel_path
                
                # Skip if the source doesn't exist in temp (shouldn't happen)
                if not source_path.exists():
                    continue
                
                # Make sure parent directory exists
                if not target_path.parent.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy back the directory or file
                if source_path.is_dir():
                    shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, target_path)
        
        # Clean up temporary directory
        if not dry_run and temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # Calculate the new size
        if not dry_run:
            final_size = get_dir_size(profile_path)
            total_size_after += final_size
            size_diff = initial_size - final_size
            percent_reduction = (size_diff / initial_size) * 100 if initial_size > 0 else 0
            
            print(f"  Profile {profile_name} cleaned successfully")
            print(f"  Final size: {format_size(final_size)} ({format_size(size_diff)} saved, {percent_reduction:.1f}% reduction)")
        else:
            # In dry run mode, just add initial size to total_size_after for consistent reporting
            total_size_after += initial_size
            print(f"  Profile {profile_name} would be cleaned (dry run)")
    
    # Clean up the temp profiles directory if it exists
    if not dry_run and temp_profiles_dir.exists():
        shutil.rmtree(temp_profiles_dir)
        if verbose:
            print(f"\nCleaned up temporary directory: {temp_profiles_dir}")
    
    # Final report
    if not dry_run:
        total_saved = total_size_before - total_size_after
        percent_saved = (total_saved / total_size_before) * 100 if total_size_before > 0 else 0
        
        print("\n" + "="*50)
        print(f"CLEANING COMPLETE - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        print(f"Total initial size: {format_size(total_size_before)}")
        print(f"Total final size: {format_size(total_size_after)}")
        print(f"Total space saved: {format_size(total_saved)} ({percent_saved:.1f}% reduction)")
        print("="*50)
    else:
        print("\nDry run completed - no changes were made")

if __name__ == "__main__":
    # Set hardcoded values directly
    profiles_dir = r"C:\Users\Nickl\AppData\Local\ms-playwright\User_profiles"
    base_profile = "no_extensions"
    dry_run = False  # Set to True to test without making changes
    verbose = True
    
    # Confirm before proceeding
    if not dry_run:
        print(f"WARNING: This will clean all profiles in {profiles_dir}")
        print(f"Base profile '{base_profile}' will be used as a clean reference")
        print("Only unique files not present in the base profile will be preserved")
        confirmation = input("Do you want to continue? (y/n): ")
        
        if confirmation.lower() != 'y':
            print("Operation cancelled.")
            exit(0)
    
    clean_profiles(
        profiles_dir, 
        base_profile=base_profile, 
        dry_run=dry_run,
        verbose=verbose
    )
