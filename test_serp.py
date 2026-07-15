import requests
import json
from config import SERPAPI_KEY

resp = requests.get("https://serpapi.com/search", params={"q": "\"Zomato\" competitors OR alternatives", "api_key": SERPAPI_KEY})
data = resp.json()
print("Organic domains:")
for r in data.get("organic_results", []):
    print(r.get("link"))
