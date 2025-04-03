import os
import re
import pytesseract
import cv2
import logging
import json


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Phrases that indicate bot detection, CAPTCHAs, or errors
BOT_DETECTION_PHRASES = [
    "access denied", 
    "blocked", 
    "403 error", 
    "forbidden",
    "the request could not be satisfied", 
    "application error",
    "too many requests",
    "rate limit",
    "suspicious activity"
]

CAPTCHA_PHRASES = [
    "captcha", 
    "verify you are human",
    "verify that you are human", 
    "i'm not a robot", 
    "i am not a robot",
    "jeg er ikke en robot",
    "help us verify",
    "prove you're human",
    "security check",
    "verification",
    "we just need to make sure",
    "ikke er en robot",
    "try different image",
    "verificerer",
    "at du er menneske",
    "recaptcha"
]

ERROR_PHRASES = [
    "404", 
    "not found", 
    "error",
    "page doesn't exist",
    "something went wrong",
    "server error",
    "500",
    "unavailable",
    "cannot connect",
    "connection refused",
    "an error occurred",
]

def extract_text_from_image(image_path):
    """Extract text from an image using grayscale preprocessing and PSM 3"""
    try:
        # Read the image with OpenCV for preprocessing
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Could not load image: {image_path}")
            return ""
        
        # Convert to grayscale (best preprocessing method based on testing)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Use PSM 3 (fully automatic page segmentation)
        text = pytesseract.image_to_string(
            gray, 
            config='--psm 3 --oem 3'
        )
        
        # Clean up the text
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    except Exception as e:
        logger.error(f"Error extracting text from {image_path}: {e}")
        return ""

def check_page_loaded(screenshot_path):
    """
    Check if a page has loaded properly based on screenshot analysis
    
    Args:
        screenshot_path: Path to the screenshot image
        
    Returns:
        dict: Results including:
            - loaded: Boolean indicating if the page loaded properly
            - status: Description of the status (loaded, bot_detected, captcha, error, or not_loaded)
            - word_count: Number of words detected in the image
            - detected_phrases: List of suspicious phrases found (if any)
    """
    # Extract text from screenshot
    text = extract_text_from_image(screenshot_path)
    
    # Clean and split the text
    words = re.findall(r'\b\w+\b', text.lower())
    word_count = len(words)
    
    # Initialize result
    result = {
        "loaded": False,
        "status": "unknown",
        "word_count": word_count,
        "detected_phrases": [],
        "text": text[:50] + "..."
    }
    
    # Check for bot detection
    for phrase in BOT_DETECTION_PHRASES:
        if phrase.lower() in text.lower():
            result["detected_phrases"].append(phrase)
            result["status"] = "bot_detected"
            return result
    
    # Check for CAPTCHA
    for phrase in CAPTCHA_PHRASES:
        if phrase.lower() in text.lower():
            result["detected_phrases"].append(phrase)
            result["status"] = "captcha"
            return result
    
    # Check for errors
    for phrase in ERROR_PHRASES:
        if phrase.lower() in text.lower():
            result["detected_phrases"].append(phrase)
            result["status"] = "error"
            return result
    
    # Check if the page has enough content to be considered loaded
    if word_count < 2:
        result["status"] = "not_loaded"
        return result
    
    # If we got here, the page likely loaded correctly
    result["loaded"] = True
    result["status"] = "loaded"
    return result

def check_domain_screenshots(screenshots_dir):
    """
    Check all screenshots in a domain directory
    
    Args:
        screenshots_dir: Path to the screenshots directory
        
    Returns:
        dict: Results for all screenshots
    """
    results = {}
    
    # Get all screenshot files
    screenshot_files = [f for f in os.listdir(screenshots_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not screenshot_files:
        logger.warning(f"No screenshots found in {screenshots_dir}")
        return results
    
    # Group screenshots by visit
    visit_pattern = re.compile(r'visit(\d+)')
    visits = {}
    
    for file in screenshot_files:
        match = visit_pattern.search(file)
        if match:
            visit_num = match.group(1)
            if visit_num not in visits:
                visits[visit_num] = []
            visits[visit_num].append(file)
        else:
            # Files without visit number go to "unknown" group
            if "unknown" not in visits:
                visits["unknown"] = []
            visits["unknown"].append(file)
    
    # Process each visit without progress bars
    for visit_num, files in visits.items():
        results[f"visit{visit_num}"] = {}
        
        # Process each file without tqdm
        for file in files:
            file_path = os.path.join(screenshots_dir, file)
            result = check_page_loaded(file_path)
            results[f"visit{visit_num}"][file] = result
    
    return results

def check_all_domains(screenshots_base_dir, output_file=None):
    """
    Check all domains in the screenshots base directory
    
    Args:
        screenshots_base_dir: Path to the directory containing domain folders
        output_file: Optional path to save results as JSON
        
    Returns:
        dict: Results for all domains
    """
    all_results = {}
    
    # Get all domain directories
    domain_dirs = [d for d in os.listdir(screenshots_base_dir) 
                  if os.path.isdir(os.path.join(screenshots_base_dir, d))]
    
    if not domain_dirs:
        logger.warning(f"No domain directories found in {screenshots_base_dir}")
        return all_results
    
    # Process each domain without progress bars
    for domain in domain_dirs:
        logger.info(f"Processing domain: {domain}")
        domain_dir = os.path.join(screenshots_base_dir, domain)
        domain_results = check_domain_screenshots(domain_dir)
        all_results[domain] = domain_results
    
    # Save results to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    
    return all_results

def test_domain(screenshots_base_dir, domain_name):
    """Test a specific domain and print results"""
    domain_dir = os.path.join(screenshots_base_dir, domain_name)
    if os.path.exists(domain_dir):
        results = check_domain_screenshots(domain_dir)
        print(json.dumps(results, indent=2))
        return results
    else:
        logger.error(f"Domain screenshots directory not found: {domain_dir}")
        return None

if __name__ == "__main__":
    # Simple configuration - edit these values to run different functions
    SCREENSHOTS_BASE_DIR = "data/banner_data/screenshots"
    OUTPUT_FILE = "page_loading_results.json"
    
    # To test a single domain, set TEST_DOMAIN to the domain name
    # To process all domains, leave it as None
    TEST_DOMAIN = "reuters.com"  # or None
    
    if TEST_DOMAIN:
        print(f"Testing domain: {TEST_DOMAIN}")
        test_domain(SCREENSHOTS_BASE_DIR, TEST_DOMAIN)
    else:
        results = check_all_domains(SCREENSHOTS_BASE_DIR, OUTPUT_FILE)