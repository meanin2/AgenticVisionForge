import re
import requests
import time
import google.generativeai as genai

def remove_think_tags(text):
    """
    Removes <think>...</think> blocks, often used in chain-of-thought,
    leaving just the final user-facing response.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def unload_model(model_name):
    """Unload a model from Ollama's memory."""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "keep_alive": 0
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Model {model_name} unloaded successfully")
        else:
            print(f"Failed to unload model {model_name}")
    except Exception as e:
        print(f"Error unloading model {model_name}: {e}")

def generate_text_ollama(prompt, config, system=None):
    """Generate text using Ollama."""
    payload = {
        "model": config["text"]["ollama"]["model"],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7}
    }
    if system:
        payload["system"] = system

    try:
        r = requests.post(config["text"]["ollama"]["api_url"], json=payload)
        r.raise_for_status()
        text = r.json().get("response", "")
        if config["text"]["ollama"].get("strip_think_tags", False):
            text = remove_think_tags(text)
        return text
    except Exception as e:
        print(f"[generate_text] Ollama error: {e}")
        return ""
    finally:
        # Unload the model after use
        unload_model(config["text"]["ollama"]["model"])
        time.sleep(2)

def generate_text_gemini(prompt, config, system=None):
    """Generate text using Gemini."""
    try:
        # Configure Gemini
        genai.configure(api_key=config["text"]["gemini"]["api_key"])
        
        # Load the model
        model = genai.GenerativeModel(config["text"]["gemini"]["model"])
        
        # Generate content
        if system:
            model = genai.GenerativeModel(
                model_name=config["text"]["gemini"]["model"],
                system_instruction=system
            )
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[generate_text] Gemini error: {e}")
        return ""
    finally:
        time.sleep(2)

def refine_prompt(original_prompt, analysis, config):
    """
    Creates a refined prompt using the configured text model. 
    We pass:
    - The original prompt
    - The analysis feedback
    - A system prompt instructing how to refine
    """
    system_message = (
        "You are a prompt refinement assistant. Given an original prompt and feedback, "
        "improve the prompt. Retain the core concept. Respond only with the improved prompt."
    )

    combined_prompt = (
        f"Original prompt: {original_prompt}\n"
        f"Feedback: {analysis}\n"
        f"Improved prompt:"
    )

    provider = config["text"]["provider"]
    
    if provider == "ollama":
        return generate_text_ollama(combined_prompt, config, system=system_message)
    elif provider == "gemini":
        return generate_text_gemini(combined_prompt, config, system=system_message)
    else:
        raise ValueError(f"Unsupported text provider: {provider}") 