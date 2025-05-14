#!/usr/bin/env python3
import json
import base64
import os

def extract_and_clean_screenshots(json_file="data.json", output_dir="screenshots"):
    """
    Extract base64-encoded screenshots from a JSON file, save them as images,
    and clean the JSON file by removing the screenshot data.
    
    Args:
        json_file (str): Path to the JSON file
        output_dir (str): Directory to save the extracted images
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Read the JSON file
        with open(json_file, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        
        # Track if we modified anything
        modified = False
        
        # Extract screenshots from ScreenshotGatherer
        if 'data' in data and 'ScreenshotGatherer' in data['data']:
            screenshot_data = data['data']['ScreenshotGatherer']
            
            # Extract and save onDomContentLoaded screenshot
            if 'onDomContentLoaded' in screenshot_data:
                # Get the base64 data
                base64_data = screenshot_data['onDomContentLoaded']
                if '...(line too long; chars omitted)' in base64_data:
                    print("Warning: 'onDomContentLoaded' data is truncated and won't produce a valid image")
                
                # Save the image
                save_base64_as_image(base64_data, os.path.join(output_dir, "screenshot_onDomContentLoaded.png"))
                
                # Replace the base64 data with a placeholder
                data['data']['ScreenshotGatherer']['onDomContentLoaded'] = "[SCREENSHOT EXTRACTED]"
                modified = True
            
            # Extract and save onPageWait screenshot
            if 'onPageWait' in screenshot_data:
                # Get the base64 data
                base64_data = screenshot_data['onPageWait']
                if '...(line too long; chars omitted)' in base64_data:
                    print("Warning: 'onPageWait' data is truncated and won't produce a valid image")
                
                # Save the image
                save_base64_as_image(base64_data, os.path.join(output_dir, "screenshot_onPageWait.png"))
                
                # Replace the base64 data with a placeholder
                data['data']['ScreenshotGatherer']['onPageWait'] = "[SCREENSHOT EXTRACTED]"
                modified = True
            
        # Extract DOM screenshot if present
        if 'data' in data and 'DOMGatherer' in data['data'] and 'dom' in data['data']['DOMGatherer']:
            dom_data = data['data']['DOMGatherer']['dom']
            
            # Check if DOM data is large and looks like it contains encoded content
            if len(dom_data) > 1000:
                # Save the DOM to a file
                with open(os.path.join(output_dir, "dom.html"), 'w', encoding='utf-8') as f:
                    f.write(dom_data)
                
                # Replace with placeholder
                data['data']['DOMGatherer']['dom'] = "[DOM EXTRACTED]"
                modified = True
                print(f"Saved DOM content to {os.path.join(output_dir, 'dom.html')}")
            
        # Save the modified JSON if changes were made
        if modified:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"Updated {json_file} with placeholders for extracted content")
        
        print(f"Screenshots extracted to {output_dir} directory")
            
    except Exception as e:
        print(f"Error extracting screenshots: {str(e)}")
        
def save_base64_as_image(base64_data, output_file):
    """
    Decode base64 string and save it as an image file.
    
    Args:
        base64_data (str): Base64-encoded image data
        output_file (str): Path to save the image
    """
    try:
        # Remove truncation markers if present
        if '...(line too long; chars omitted)' in base64_data:
            base64_data = base64_data.split('...(line too long; chars omitted)')[0]
        
        # Decode the base64 data
        image_data = base64.b64decode(base64_data)
        
        # Write the binary data to a file
        with open(output_file, 'wb') as f:
            f.write(image_data)
            
        print(f"Saved image to {output_file}")
    except Exception as e:
        print(f"Error saving image {output_file}: {str(e)}")

# Run the extraction and cleaning
if __name__ == "__main__":
    extract_and_clean_screenshots() 