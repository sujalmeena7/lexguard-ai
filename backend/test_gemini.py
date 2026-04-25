"""Quick test of Gemini model + JSON output."""
import google.generativeai as genai
import json

import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'))

# Test 1: With response_mime_type
print("--- Test 1: response_mime_type=application/json ---")
try:
    resp = model.generate_content(
        'Return a JSON object with key "status" set to "ok" and key "score" set to 42. Return ONLY the JSON, nothing else.',
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
    )
    print(f"Raw text: {repr(resp.text[:500])}")
    data = json.loads(resp.text)
    print(f"Parsed: {data}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Without response_mime_type
print("\n--- Test 2: No response_mime_type ---")
try:
    resp = model.generate_content(
        'Return a JSON object with key "status" set to "ok" and key "score" set to 42. Return ONLY the JSON, nothing else.',
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
        )
    )
    print(f"Raw text: {repr(resp.text[:500])}")
except Exception as e:
    print(f"Error: {e}")
