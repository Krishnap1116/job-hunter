# test_api.py

import anthropic
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

print(f"API Key present: {bool(ANTHROPIC_API_KEY)}")
print(f"API Key starts with: {ANTHROPIC_API_KEY[:15] if ANTHROPIC_API_KEY else 'NONE'}...")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

try:
    response = client.messages.create(
        model=" claude-3-haiku-20240307",
        max_tokens=100,
        messages=[{"role": "user", "content": "Say hello"}]
    )
    
    print("✅ API works!")
    print(f"Response: {response.content[0].text}")
    
except Exception as e:
    print(f"❌ API Error: {e}")