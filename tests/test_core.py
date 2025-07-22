from bs4 import BeautifulSoup
from site_cloner.core import extract_resources

def test_extract_resources():
    html = """
    <html>
      <head><link href='style.css' rel='stylesheet'></head>
      <body><img src='image.jpg'><script src='script.js'></script></body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    exts = ['.css', '.jpg', '.js']
    resources = extract_resources(soup, 'https://example.com', exts)
    assert 'https://example.com/style.css' in resources
    assert 'https://example.com/image.jpg' in resources
    assert 'https://example.com/script.js' in resources
