#!/usr/bin/env python3
import json
import os

def format_json_file(file_path="data.json", indent=2):
    """
    Format a JSON file with proper indentation.
    
    Args:
        file_path (str): Path to the JSON file (default: data.json)
        indent (int): Number of spaces for indentation
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"Error: File not found - {file_path}")
            return False
            
        # Read the JSON file with UTF-8 encoding
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        
        # Format the JSON with proper indentation
        formatted_json = json.dumps(data, indent=indent, sort_keys=False)
        
        # Save the formatted JSON back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(formatted_json)
            
        print(f"Formatted JSON saved to {file_path}")
        return True
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in {file_path}")
        print(f"Details: {str(e)}")
        print("Tip: This might not be a valid JSON file or it might contain binary data.")
        return False
    except IOError as e:
        print(f"Error: Could not read/write file - {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

# Run the formatting function on data.json
if __name__ == "__main__":
    format_json_file()
