import json
import requests

def generate_text(prompt, model, system=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7}
    }
    if system:
        payload["system"] = system
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload
        )
        return response.json()["response"]
    except Exception as e:
        print(f"Ollama API error: {str(e)}")
        return ""

def refine_prompt(original_prompt, analysis):
    refinement_system = """You are a prompt refinement assistant. Given an original prompt and 
    critical feedback, generate an improved version that addresses the feedback while maintaining
    the core concept. Respond only with the new prompt."""
    
    return generate_text(
        f"Original prompt: {original_prompt}\nFeedback: {analysis}\nImproved prompt:",
        "llama3",
        refinement_system
    )
