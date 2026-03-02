import os
import requests
import json
from dotenv import load_dotenv

def test_oanda_auth():
    """
    Test script to verify OANDA v20 API credentials.
    Connects to the accounts summary endpoint to validate tokens.
    """
    # Load Environment Variables securely
    load_dotenv()
    
    api_key = os.getenv("OANDA_ACCESS_TOKEN")
    account_id = os.getenv("OANDA_ACCOUNT_ID")
    base_url = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    
    if not api_key or not account_id:
        print("[FAIL] Missing OANDA credentials in .env file.")
        return
        
    url = f"{base_url}/v3/accounts/{account_id}/summary"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"[TEST] Testing OANDA Connection to: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("[SUCCESS] OANDA Auth Connection Established!")
            data = response.json()
            account = data.get("account", {})
            print(f"Account Balance: {account.get('balance', 'N/A')} {account.get('currency', '')}")
            print(f"Margin Rate: {account.get('marginRate', 'N/A')}")
        else:
            print(f"[HTTP ERROR {response.status_code}] Connection Failed.")
            print("Response:", response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"[NETWORK ERROR] {e}")

if __name__ == "__main__":
    test_oanda_auth()
