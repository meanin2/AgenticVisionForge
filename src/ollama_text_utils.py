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

def refine_prompt(original_prompt, analysis, config, iteration=1, previous_iterations=None):
    """
    Creates a refined prompt using the configured text model.
    Adapts the strategy based on iteration number and includes full history.
    """
    if previous_iterations is None:
        previous_iterations = []

    if iteration == 1:
        system_message = (
            "You are a prompt refinement assistant for image generation. "
            "For this first iteration, focus on expanding and enriching the initial prompt "
            "with more specific details about composition, lighting, and atmosphere. "
            "Maintain the core concept but add depth to the description."
        )

        combined_prompt = (
            f"Original prompt: {original_prompt}\n"
            f"First analysis: {analysis}\n"
            f"Please enhance this prompt with more specific details while maintaining its core concept. "
            f"Focus on adding clear descriptions of composition, lighting, and atmosphere.\n"
            f"Refined prompt:"
        )
    elif iteration == 2:
        # For second iteration, analyze what worked and what didn't in first attempt
        prev_iter = previous_iterations[0]
        system_message = (
            "You are a prompt refinement assistant for image generation. "
            "For this second iteration, analyze the differences between the first two attempts "
            "and adjust the prompt based on what elements were successful or unsuccessful. "
            "Focus on strengthening what worked and fixing what didn't."
        )

        combined_prompt = (
            f"Original goal: {prev_iter.get('goal', 'Unknown goal')}\n"
            f"Iteration history:\n"
            f"1. First prompt: {prev_iter.get('prompt_before', '')}\n"
            f"   Analysis: {prev_iter.get('analysis', '')}\n"
            f"2. Current prompt: {original_prompt}\n"
            f"   Current analysis: {analysis}\n\n"
            f"Based on these two iterations, create a refined prompt that:\n"
            f"1. Strengthens elements that showed improvement\n"
            f"2. Addresses consistent issues\n"
            f"3. Maintains successful aspects from both attempts\n"
            f"Refined prompt:"
        )
    else:
        # For third and subsequent iterations, use full history to make informed decisions
        system_message = (
            "You are a prompt refinement assistant for image generation. "
            "Analyze the complete history of iterations to identify patterns, "
            "successful elements, and areas needing improvement. "
            "Use this comprehensive understanding to create an optimal prompt."
        )

        history_text = "\n".join([
            f"{i+1}. Prompt: {iter.get('prompt_before', '')}\n"
            f"   Analysis: {iter.get('analysis', '')}"
            for i, iter in enumerate(previous_iterations)
        ])

        combined_prompt = (
            f"Original goal: {previous_iterations[0].get('goal', 'Unknown goal')}\n"
            f"Complete iteration history:\n{history_text}\n"
            f"Current prompt: {original_prompt}\n"
            f"Current analysis: {analysis}\n\n"
            f"Based on this complete history:\n"
            f"1. Identify what elements consistently work well\n"
            f"2. Address any persistent issues\n"
            f"3. Incorporate successful patterns from previous iterations\n"
            f"4. Avoid approaches that didn't yield improvements\n"
            f"Create an optimized prompt that synthesizes these learnings:\n"
            f"Refined prompt:"
        )

    provider = config["text"]["provider"]
    
    if provider == "ollama":
        return generate_text_ollama(combined_prompt, config, system=system_message)
    elif provider == "gemini":
        return generate_text_gemini(combined_prompt, config, system=system_message)
    else:
        raise ValueError(f"Unsupported text provider: {provider}") 