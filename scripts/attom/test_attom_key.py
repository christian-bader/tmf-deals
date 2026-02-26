import requests, os, json
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

resp = requests.get(
    f"{BASE}/property/detail",
    headers={"Accept": "application/json", "apikey": API_KEY},
    params={"address1": "4529 Winona Ave", "address2": "San Diego, CA 92115"},
)
print(f"HTTP {resp.status_code}")
print(json.dumps(resp.json(), indent=2)[:500])
