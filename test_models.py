import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("NO API KEY")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)
print(response.status_code)
if response.status_code == 200:
    models = response.json().get('models', [])
    for m in models:
        print(m['name'])
else:
    print(response.text)
