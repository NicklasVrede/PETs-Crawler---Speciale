import os
import re
import pytesseract
import cv2
import numpy as np
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_with_preprocessing(image_path, psm_mode, preprocessing='grayscale'):
    """
    Extract text from an image using a specific PSM mode and preprocessing technique
    
    Args:
        image_path: Path to the image
        psm_mode: Tesseract PSM mode
        preprocessing: Preprocessing technique to apply
            - 'none': No preprocessing
            - 'grayscale': Convert to grayscale
            - 'threshold': Binary thresholding
            - 'adaptive': Adaptive thresholding
            - 'blur': Gaussian blur + thresholding
            - 'contrast': Increase contrast
    """
    try:
        # Read the image with OpenCV
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Could not load image: {image_path}")
            return ""
        
        # Apply preprocessing
        if preprocessing == 'none':
            # No preprocessing, use original
            processed_img = img
        elif preprocessing == 'grayscale':
            # Convert to grayscale
            processed_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif preprocessing == 'threshold':
            # Apply binary thresholding
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, processed_img = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        elif preprocessing == 'adaptive':
            # Apply adaptive thresholding
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            processed_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                 cv2.THRESH_BINARY, 11, 2)
        elif preprocessing == 'blur':
            # Apply Gaussian blur + thresholding
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, processed_img = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif preprocessing == 'contrast':
            # Increase contrast
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced_lab = cv2.merge((cl, a, b))
            processed_img = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            processed_img = cv2.cvtColor(processed_img, cv2.COLOR_BGR2GRAY)
        else:
            logger.warning(f"Unknown preprocessing method: {preprocessing}, using grayscale")
            processed_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Use PIL for tesseract
        if len(processed_img.shape) == 3:  # Color image
            processed_img = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(processed_img)
        else:  # Grayscale
            pil_img = Image.fromarray(processed_img)
        
        # Use specified PSM mode
        text = pytesseract.image_to_string(
            pil_img, 
            config=f'--psm {psm_mode} --oem 3'
        )
        
        # Clean up the text
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    except Exception as e:
        logger.error(f"Error extracting text from {image_path} with PSM {psm_mode} and {preprocessing}: {e}")
        return ""

def count_words(text):
    """Count the number of words in text"""
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)

def test_psm_with_preprocessing(image_path):
    """Test various PSM modes with different preprocessing techniques"""
    # PSM modes to test
    psm_modes = [3, 6, 11]  # Limiting to most common for webpages
    
    # Preprocessing methods to test
    preprocessing_methods = ['none', 'grayscale', 'threshold', 'adaptive', 'blur', 'contrast']
    
    # Dictionary to store results
    results = {}
    
    print(f"Testing PSM modes with preprocessing on image: {os.path.basename(image_path)}\n")
    print("=" * 80)
    
    # Test each combination
    for preproc in preprocessing_methods:
        print(f"\n\n=========== PREPROCESSING: {preproc.upper()} ===========\n")
        
        for psm in psm_modes:
            key = f"{preproc}_psm{psm}"
            text = extract_text_with_preprocessing(image_path, psm, preproc)
            word_count = count_words(text)
            
            results[key] = {
                "preprocessing": preproc,
                "psm": psm,
                "word_count": word_count,
                "text": text
            }
            
            # Print results
            print(f"\nPSM {psm} with {preproc} preprocessing:")
            print(f"Word count: {word_count}")
            print("-" * 40)
            print(f"Full text extract:")
            print(text)
            print("=" * 80)
    
    # Find the combination with the highest word count
    best_combo = max(results.items(), key=lambda x: x[1]["word_count"])
    best_key = best_combo[0]
    best_result = best_combo[1]
    
    print(f"\nBest combination: {best_key}")
    print(f"Preprocessing: {best_result['preprocessing']}")
    print(f"PSM mode: {best_result['psm']}")
    print(f"Word count: {best_result['word_count']}")
    
    return results

if __name__ == "__main__":
    # Path to the image file
    image_path = "data/banner_data/screenshots/active.com/visit0_accept_all_cookies.png"
    
    # Test different PSM modes with preprocessing
    results = test_psm_with_preprocessing(image_path) 