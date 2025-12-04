import io
import requests
from PIL import Image, ImageDraw, ImageFont

# Create a simple test image (a colored rectangle with text)
img = Image.new('RGB', (300, 450), color=(73, 109, 137))
d = ImageDraw.Draw(img)
d.text((10, 10), "Test Cover", fill=(255, 255, 0))

# Save to bytes
buf = io.BytesIO()
img.save(buf, format='JPEG')
buf.seek(0)

files = {'image': ('test_cover.jpg', buf, 'image/jpeg')}

url = 'http://127.0.0.1:8000/api/visual-search/'
try:
    resp = requests.post(url, files=files, timeout=15)
    print('Status code:', resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)
except Exception as e:
    print('Request failed:', e)
