import base64
import requests
import os
import time
import google.generativeai as genai
from PIL import Image
from .ollama_text_utils import unload_model

def analyze_image_ollama(image_path, config, stage="describe"):
    """Use Ollama for image analysis. Returns dict with system/user/response."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode()

    if stage == "describe":
        system_message = (
            "You are an expert art critic and visual analyst. "
            "Describe this image in comprehensive detail, focusing on all visual elements present. "
            "Do not compare it to any goal or make suggestions - just describe what you see."
        )
        prompt = "Provide a detailed description of this image, including all visual elements, composition, lighting, colors, and mood."
    else:  # stage == "analyze"
        system_message = (
            "You are a quality assurance expert. Compare this image to the goal and create two lists:\n"
            "1. Elements that align with the goal\n"
            "2. Elements that don't align or need improvement"
        )
        prompt = (
            f"Goal: {config.get('current_goal', '')}\n"
            f"Previous Description: {config.get('image_description', '')}\n\n"
            f"Create two lists comparing this image to the goal:\n"
            f"1. Elements that align with the goal\n"
            f"2. Elements that don't align or need improvement"
        )

    payload = {
        "model": config["vision"]["ollama"]["model"],
        "prompt": prompt,
        "system": system_message,
        "images": [image_b64],
        "stream": False
    }
    try:
        resp = requests.post(config["vision"]["ollama"]["api_url"], json=payload)
        resp.raise_for_status()
        text = resp.json().get("response", "")
        return {
            "system_prompt": system_message,
            "user_prompt": prompt,
            "response": text
        }
    except Exception as e:
        print(f"[analyze_image] Error analyzing {os.path.basename(image_path)}: {e}")
        return {
            "system_prompt": system_message,
            "user_prompt": prompt,
            "response": f"Error: {str(e)}"
        }
    finally:
        unload_model(config["vision"]["ollama"]["model"])
        time.sleep(2)

def analyze_image_gemini(image_path, config, stage="describe"):
    """Use Gemini for image analysis. Returns dict with system/user/response."""
    try:
        # Configure Gemini
        genai.configure(api_key=config["vision"]["gemini"]["api_key"])
        
        # Load the model
        model = genai.GenerativeModel(config["vision"]["gemini"]["model"])
        
        image = Image.open(image_path)

        if stage == "describe":
            system_message = (
                "You are an expert art critic and visual analyst. "
                "Describe this image in comprehensive detail, focusing on all visual elements present. "
                "Do not compare it to any goal or make suggestions - just describe what you see."
            )
            prompt_text = "Provide a detailed description of this image, including all visual elements, composition, lighting, colors, and mood."
        else:  # stage == "analyze"
            system_message = (
                "You are a quality assurance expert. Compare this image to the goal and create two lists:\n"
                "1. Elements that align with the goal\n"
                "2. Elements that don't align or need improvement"
            )
            prompt_text = (
                f"Goal: {config.get('current_goal', '')}\n"
                f"Previous Description: {config.get('image_description', '')}\n\n"
                f"Create two lists comparing this image to the goal:\n"
                f"1. Elements that align with the goal\n"
                f"2. Elements that don't align or need improvement"
            )

        full_prompt = f"{system_message}\n\nUser: {prompt_text}"
        response = model.generate_content([image, full_prompt])
        text = response.text

        return {
            "system_prompt": system_message,
            "user_prompt": prompt_text,
            "response": text
        }
    except Exception as e:
        print(f"[analyze_image] Error analyzing {os.path.basename(image_path)} with Gemini: {e}")
        return {
            "system_prompt": "Gemini system message (error fallback)",
            "user_prompt": "Gemini user prompt (error fallback)",
            "response": f"Error: {str(e)}"
        }
    finally:
        time.sleep(2)

def analyze_image(image_path, config, stage="describe"):
    """
    Analyze an image using either Ollama or Gemini based on configuration.
    Returns dict with {system_prompt, user_prompt, response}.
    """
    provider = config["vision"]["provider"]
    
    if provider == "ollama":
        return analyze_image_ollama(image_path, config, stage)
    elif provider == "gemini":
        return analyze_image_gemini(image_path, config, stage)
    else:
        raise ValueError(f"Unsupported vision provider: {provider}")
