import os
import google.generativeai as genai

api_key = os.getenv("GOOGLE_API_KEY", "").strip()
if not api_key:
    raise RuntimeError("Defina a variavel de ambiente GOOGLE_API_KEY antes de executar.")

genai.configure(api_key=api_key)

print("Modelos disponíveis:")
for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(f"  - {model.name} ({model.display_name})")
