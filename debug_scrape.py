import requests

url = "https://www.100ppi.com/mprice/plist-1-369-1.html"
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    resp = requests.get(url, headers=headers)
    resp.encoding = 'utf-8'
    print(resp.text[:4000]) # Print first 4000 chars to see structure
except Exception as e:
    print(e)
