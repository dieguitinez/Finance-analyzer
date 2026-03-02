from google import genai
import os

def test_genai_import():
    try:
        # We don't need a real key just to see if the client initializes syntactically 
        # (though some checks might happen on init).
        client = genai.Client(api_key="TEST_KEY")
        print("✅ google-genai Client initialized successfully (Syntactic check)")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize genai.Client: {e}")
        return False

if __name__ == "__main__":
    test_genai_import()
