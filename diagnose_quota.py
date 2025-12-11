
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

print(f"🔑 Testing API Key: ...{api_key[-5:] if api_key else 'None'}")
genai.configure(api_key=api_key)

print("\n1️⃣ Checking Available Models...")
available_models = []
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            print(f"   - {m.name}")
except Exception as e:
    print(f"   ❌ Error listing models: {e}")

print("\n2️⃣ Testing Gemini 2.5 Flash (Target)...")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    res = model.generate_content("Hello")
    print("   ✅ Success! (Quota OK)")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n3️⃣ Testing Gemini 2.5 Preview (Alternative)...")
try:
    model = genai.GenerativeModel("gemini-2.5-computer-use-preview-10-2025")
    res = model.generate_content("Hello")
    print("   ✅ Success! (Quota OK)")
except Exception as e:
    print(f"   ❌ Failed: {e}")
