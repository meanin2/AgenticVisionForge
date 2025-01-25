import base64
import requests
import os
import time
import google.generativeai as genai
from PIL import Image
from .ollama_text_utils import unload_model

def analyze_image_ollama(image_path, config):
    """Use Ollama for image analysis."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": config["vision"]["ollama"]["model"],
        "prompt": config["analysis_prompt"],
        "images": [image_b64],
        "stream": False
    }
    try:
        resp = requests.post(config["vision"]["ollama"]["api_url"], json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        print(f"[analyze_image] Error analyzing {os.path.basename(image_path)}: {e}")
        return ""
    finally:
        # Unload the vision model after use
        unload_model(config["vision"]["ollama"]["model"])
        # Add a 2-second pause after analysis
        time.sleep(2)

def analyze_image_gemini(image_path, config):
    """Use Gemini for image analysis."""
    try:
        # Configure Gemini
        genai.configure(api_key=config["vision"]["gemini"]["api_key"])
        
        # Load the model
        model = genai.GenerativeModel(config["vision"]["gemini"]["model"])
        
        # Load and analyze the image
        image = Image.open(image_path)
        response = model.generate_content([image, config["analysis_prompt"]])
        
        return response.text
    except Exception as e:
        print(f"[analyze_image] Error analyzing {os.path.basename(image_path)} with Gemini: {e}")
        return ""
    finally:
        time.sleep(2)  # Add a pause after analysis

def analyze_image(image_path, config):
    """
    Analyze an image using either Ollama or Gemini based on configuration.
    Returns the LLM's textual feedback or an empty string on error.
    """
    provider = config["vision"]["provider"]
    
    if provider == "ollama":
        return analyze_image_ollama(image_path, config)
    elif provider == "gemini":
        return analyze_image_gemini(image_path, config)
    else:
        raise ValueError(f"Unsupported vision provider: {provider}") 