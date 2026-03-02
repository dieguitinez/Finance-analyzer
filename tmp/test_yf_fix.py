import os
import yfinance as yf
import json
from dotenv import load_dotenv
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.self_healer import NivoSelfHealer

load_dotenv()

def test_yf():
    print("--- Testing Yahoo Finance ---")
    try:
        df = yf.download("EURUSD=X", period="1d", interval="1m", progress=False)
        if df.empty:
            print("[FAIL] Error: Downloaded dataframe is empty.")
        else:
            print(f"[OK] Success: Downloaded {len(df)} rows.")
            # print(df.tail(2).to_json())
    except Exception as e:
        print(f"[FAIL] Exception during YF download: {e}")

def test_ai():
    print("\n--- Testing AI Diagnostics ---")
    try:
        diag = NivoSelfHealer.diagnose_with_ai("Test error: Connection timeout", "Context: Dummy test")
        print(f"AI Response: {diag}")
        if "Gemini API no configurada" in diag or "Error consultando a la IA" in diag:
            print("[FAIL] Error: AI Diagnostic returned a failure message.")
        else:
            print("[OK] Success: AI Diagnostic working.")
    except Exception as e:
        print(f"[FAIL] AI Diagnostic throw an exception: {e}")

if __name__ == "__main__":
    api_key = os.getenv('GOOGLE_API_KEY') or ''
    print(f"GOOGLE_API_KEY snippet: {api_key[:10]}...")
    test_yf()
    test_ai()
