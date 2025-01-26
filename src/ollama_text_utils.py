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

def extract_prompt_tags(text):
    """
    Extract content between <prompt></prompt> tags.
    Returns None if no tags are found.
    """
    match = re.search(r'<prompt>(.*?)</prompt>', text, re.DOTALL)
    return match.group(1).strip() if match else None

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
        if system:
            model = genai.GenerativeModel(
                model_name=config["text"]["gemini"]["model"],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7
                )
            )
            # Combine system and user message
            prompt = f"{system}\n\nUser: {prompt}"
        else:
            model = genai.GenerativeModel(config["text"]["gemini"]["model"])
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[generate_text] Gemini error: {e}")
        return ""
    finally:
        time.sleep(2)

def understand_goal(goal, config):
    """Initial analysis of the user's goal."""
    system_message = (
        "You are an expert art director and creative consultant. "
        "Analyze the following goal for an image generation project. "
        "Break down the key visual elements, style, mood, composition, and technical aspects we need to achieve. "
        "Be specific and detailed in your analysis. "
        "Do not generate any prompts yet - focus only on analysis."
    )

    prompt = f"Goal: {goal}\n\nProvide a detailed analysis of the visual elements we need to create."
    
    provider = config["text"]["provider"]
    return generate_text_with_provider(provider, prompt, config, system_message)

def create_initial_prompt(goal, analysis, config):
    """Create the first T5 prompt based on goal analysis."""
    system_message = (
        "You are a T5 prompt engineering expert specializing in image generation. "
        "You will create a detailed prompt that captures all the analyzed elements. "
        "You can think through your process outside the prompt tags. "
        "The final prompt MUST be wrapped in <prompt></prompt> tags. "
        "Only the text within these tags will be used for image generation."
    )

    prompt = (
        f"Goal: {goal}\n\n"
        f"Analysis: {analysis}\n\n"
        f"Think through how to create a T5 prompt that captures these elements. "
        f"Explain your approach, then provide the final prompt wrapped in <prompt></prompt> tags.\n\n"
        f"Remember: Only the text within the prompt tags will be used for generation."
    )

    provider = config["text"]["provider"]
    response = generate_text_with_provider(provider, prompt, config, system_message)
    prompt_text = extract_prompt_tags(response)
    if not prompt_text:
        print("Warning: No prompt tags found in response. Using full response as prompt.")
        prompt_text = response.strip()
    return prompt_text

def generate_text_with_provider(provider, prompt, config, system=None):
    """Helper function to generate text with the configured provider."""
    if provider == "ollama":
        return generate_text_ollama(prompt, config, system=system)
    elif provider == "gemini":
        return generate_text_gemini(prompt, config, system=system)
    else:
        raise ValueError(f"Unsupported text provider: {provider}")

def refine_prompt(original_prompt, goal, image_description, alignment_analysis, config):
    """Create a refined prompt based on previous results."""
    system_message = (
        "You are a T5 prompt optimization expert. "
        "Analyze the results and create an improved prompt. "
        "Keep language that produced aligned elements, but rework sections for unaligned elements. "
        "You can think through your process outside the prompt tags. "
        "The final prompt MUST be wrapped in <prompt></prompt> tags. "
        "Only the text within these tags will be used for image generation."
    )

    prompt = (
        f"Goal: {goal}\n\n"
        f"Previous Prompt: {original_prompt}\n\n"
        f"Image Description: {image_description}\n\n"
        f"Alignment Analysis: {alignment_analysis}\n\n"
        f"Think through how to improve the prompt:\n"
        f"1. Identify what elements worked well\n"
        f"2. Determine what needs to change\n"
        f"3. Create an improved version\n\n"
        f"Explain your thinking, then provide the final prompt wrapped in <prompt></prompt> tags.\n"
        f"Remember: Only the text within the prompt tags will be used for generation."
    )

    provider = config["text"]["provider"]
    response = generate_text_with_provider(provider, prompt, config, system_message)
    prompt_text = extract_prompt_tags(response)
    if not prompt_text:
        print("Warning: No prompt tags found in response. Using full response as prompt.")
        prompt_text = response.strip()
    return prompt_text 