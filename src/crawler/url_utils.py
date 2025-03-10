from urllib.parse import urlparse, urljoin

def normalize_url(url):
    """Normalize URL by removing fragments and trailing slashes"""
    parsed = urlparse(url)
    # Remove fragments and normalize slashes
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized

def is_valid_url(url):
    """Check if URL is valid and uses http(s) scheme"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ['http', 'https']
    except:
        return False

def get_domain(url):
    """Extract domain from URL"""
    try:
        return urlparse(url).netloc.lower()
    except:
        return None 