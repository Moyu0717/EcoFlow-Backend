"""
test_gemini.py — Run this FIRST to verify your Gemini API key works.
Usage: python test_gemini.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "")

if not API_KEY:
    print("❌ GEMINI_API_KEY is not set in your .env file.")
    print("   1. Go to https://aistudio.google.com/app/apikey")
    print("   2. Create a new key")
    print("   3. Add it to your .env:  GEMINI_API_KEY=AIza...")
    exit(1)

print(f"🔑 API key found: {API_KEY[:10]}...")

# Step 1: Check package
try:
    import google.generativeai as genai
    print("✅ google-generativeai package installed")
except ImportError:
    print("❌ Package missing. Run:  pip install google-generativeai")
    exit(1)

# Step 2: Configure
genai.configure(api_key=API_KEY)

# Step 3: List available models (confirms auth works)
print("\n📋 Available Gemini models:")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"   • {m.name}")
except Exception as e:
    print(f"❌ Auth failed — {e}")
    print("\n   Common fixes:")
    print("   • Make sure the key is correct (no extra spaces)")
    print("   • Enable 'Generative Language API' in Google Cloud Console")
    print("   • If using a project-restricted key, allow 'generativelanguage.googleapis.com'")
    exit(1)

# Step 4: Test generation
print("\n🤖 Testing text generation...")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp  = model.generate_content("Say hello in Malay in one sentence.")
    print(f"✅ Gemini response: {resp.text.strip()}")
except Exception as e:
    print(f"❌ Generation failed — {e}")
    exit(1)

print("\n🎉 All checks passed! Your Gemini integration is ready.")
print("   You can now start the server:  uvicorn main:app --reload")
