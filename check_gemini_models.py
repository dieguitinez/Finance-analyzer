import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(".env")
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

with open('model_output.txt', 'w', encoding='utf-8') as f:
    try:
        models = list(genai.list_models())
        text_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        text_models.sort(key=lambda x: x.name)
        
        for m in text_models:
            f.write(f"ID: {m.name.replace('models/', '')}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
