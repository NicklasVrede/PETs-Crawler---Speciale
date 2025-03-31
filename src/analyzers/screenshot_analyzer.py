import os
import re
import pytesseract
import cv2
from collections import defaultdict
from tqdm import tqdm
from pprint import pprint


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_from_image(image_path):
    """
    Extract text from image using OCR
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Extracted text in lowercase
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Extract text from image with PSM 3 and OEM 3
    text = pytesseract.image_to_string(
        gray, 
        config='--psm 3 --oem 3'
    ).lower()
    
    return text


def analyze_screenshots(directory="data/banner_data/screenshots/active.com", verbose=False):
    # Directory path
    # Get all PNG/JPG files in the directory
    all_files = [f for f in os.listdir(directory) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    # Separate no_extension files from others
    no_extension_files = [f for f in all_files if 'no_extension' in f]
    extension_files = [f for f in all_files if 'no_extension' not in f]
    
    if verbose: 
        tqdm.write(f"Found {len(no_extension_files)} no_extension screenshots and {len(extension_files)} extension screenshots")
    
    # Initialize JSON structure
    json_results = {
        "screenshot_check": {}
    }
    
    # Group files by visit number for comparison
    visit_groups = defaultdict(lambda: {'no_extension': None, 'extensions': []})
    
    for file in no_extension_files:
        visit_match = re.search(r'visit(\d+)_no_extension', file)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['no_extension'] = file
    
    for file in extension_files:
        visit_match = re.search(r'visit(\d+)_', file)
        if visit_match:
            visit_num = visit_match.group(1)
            visit_groups[visit_num]['extensions'].append(file)
    
    # Cookie-related keywords to look for
    cookie_keywords = [
        "cookie", "consent", "accept", "reject", "decline", 
        "privacy", "gdpr", "settings", "preferences",
        "necessary", "functional", "analytics", "marketing",
        "all", "afslå", "acceptér", "alle"
    ]
    
    # Compare each no_extension file with its corresponding extension files
    for visit_num, files in visit_groups.items():
        no_ext_file = files['no_extension']
        ext_files = files['extensions']
        
        if not no_ext_file:
            continue
            
        if verbose:
            tqdm.write(f"Analyzing screenshots for Visit {visit_num}")
        
        # Initialize the visit entry in JSON
        json_results["screenshot_check"][f"visit{visit_num}"] = {
            "keywords": [],
            "extensions": {}
        }
        
        # Process the no_extension screenshot
        no_ext_path = os.path.join(directory, no_ext_file)
        try:
            no_ext_text = extract_text_from_image(no_ext_path)
            
            # Find cookie keywords in baseline image
            found_keywords = []
            for keyword in cookie_keywords:
                if keyword.lower() in no_ext_text:
                    found_keywords.append(keyword)
            
            if found_keywords:
                if verbose:
                    tqdm.write(f"Cookie keywords found in baseline: {', '.join(found_keywords)}")
                json_results["screenshot_check"][f"visit{visit_num}"]["keywords"] = found_keywords
            else:
                if verbose:
                    tqdm.write("No cookie keywords found in baseline screenshot")
        except Exception as e:
            if verbose:
                tqdm.write(f"Error processing {no_ext_file}: {e}")
            continue
        
        # For each extension file, check if these keywords are missing
        for ext_file in ext_files:
            if verbose:
                tqdm.write(f"Analyzing: {ext_file}")
            ext_path = os.path.join(directory, ext_file)
            try:
                # Extract text using the new function
                ext_text = extract_text_from_image(ext_path)
                
                # If no keywords were found in baseline, we can't determine if banner was removed
                if not found_keywords:
                    if verbose:
                        tqdm.write("No baseline keywords to compare against - can't determine if banner was removed")
                    json_results["screenshot_check"][f"visit{visit_num}"]["extensions"][ext_file] = None
                    continue
                
                # Check if keywords from baseline are missing
                missing_keywords = []
                for keyword in found_keywords:
                    if keyword.lower() not in ext_text:
                        missing_keywords.append(keyword)
                
                if missing_keywords:
                    if verbose:
                        tqdm.write(f"Keywords missing in extension screenshot: {', '.join(missing_keywords)}")
                        tqdm.write("This indicates the cookie banner was likely handled by the extension")
                    # If any keywords are missing, set the boolean to false (banner removed)
                    json_results["screenshot_check"][f"visit{visit_num}"]["extensions"][ext_file] = False
                else:
                    if verbose:
                        tqdm.write("No keywords are missing - banner may still be present")
                    # If all keywords are present, set the boolean to true (banner still present)
                    json_results["screenshot_check"][f"visit{visit_num}"]["extensions"][ext_file] = True
            except Exception as e:
                print(f"Error processing {ext_file}: {e}")
                # Mark as error in the results
                json_results["screenshot_check"][f"visit{visit_num}"]["extensions"][ext_file] = "error"
    
    return json_results


if __name__ == "__main__":
    analyze_screenshots()