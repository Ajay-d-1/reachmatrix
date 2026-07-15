import requests
import os
from dotenv import load_dotenv

load_dotenv()

serp_key = os.getenv('SERPAPI_KEY')
if serp_key:
    r = requests.get(f'https://serpapi.com/account?api_key={serp_key}')
    if r.status_code == 200:
        data = r.json()
        print(f"SerpAPI Searches Left: {data.get('plan_searches_left')}")
    else:
        print('SerpAPI Auth Failed')

apollo_key = os.getenv('APOLLO_API_KEY')
if apollo_key:
    r = requests.get(f'https://api.apollo.io/v1/auth/health?api_key={apollo_key}')
    print(f"Apollo Status: {r.status_code}")

prospeo_key = os.getenv('PROSPEO_API_KEY')
if prospeo_key:
    r = requests.post('https://api.prospeo.io/domain-search', headers={'X-KEY': prospeo_key}, json={'company': 'example.com'})
    print(f"Prospeo response: {r.status_code} - {r.text[:100]}")
