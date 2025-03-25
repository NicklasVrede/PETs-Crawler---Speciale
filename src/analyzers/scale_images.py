import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import pytesseract  # For text extraction if needed
from pathlib import Path

def resize_screenshot(image_path, target_size=(256, 256)):
    pass

def scale_image(image_path, target_size=256, display=True):
    """
    Scale an image to the target size while maintaining aspect ratio.
    
    Args:
        image_path (str): Path to the image file
        target_size (int): Target size (width or height, whichever is larger)
        display (bool): Whether to display the scaled image
        
    Returns:
        np.array: The scaled image as a numpy array
    """
    # Read the image
    if isinstance(image_path, str) or isinstance(image_path, Path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image from {image_path}")
        # Convert from BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        # Assume it's already a numpy array
        image = image_path
    
    # Get original dimensions
    height, width = image.shape[:2]
    
    # Calculate scaling factor to maintain aspect ratio
    if width >= height:
        scaling_factor = target_size / width
        new_width = target_size
        new_height = int(height * scaling_factor)
    else:
        scaling_factor = target_size / height
        new_height = target_size
        new_width = int(width * scaling_factor)
    
    # Resize the image
    scaled_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    # Display if requested
    if display:
        plt.figure(figsize=(10, 8))
        plt.subplot(1, 2, 1)
        plt.imshow(image)
        plt.title(f"Original: {width}x{height}")
        plt.axis('off')
        
        plt.subplot(1, 2, 2)
        plt.imshow(scaled_image)
        plt.title(f"Scaled: {new_width}x{new_height}")
        plt.axis('off')
        plt.tight_layout()
        plt.show()
    
    return scaled_image

# Example usage (uncomment to test with a specific image)
# if __name__ == "__main__":
#     scaled = scale_image("path/to/your/screenshot.png")