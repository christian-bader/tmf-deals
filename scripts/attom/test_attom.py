import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

headers = {
    "Accept": "application/json",
    "apikey": API_KEY,
}

params = {
    "geoID": "CO06073",
    "minSaleAmt": 1000000,
    "maxSaleAmt": 10000000,
    "startSaleSearchDate": "2024/01/01",
    "endSaleSearchDate": "2024/03/01",
    "pageSize": 2,
    "page": 1,
}

resp = requests.get(f"{BASE_URL}/sale/detail", headers=headers, params=params)
print(f"Status: {resp.status_code}")
data = resp.json()
print(json.dumps(data, indent=2)[:5000])
