import base64
import requests

def analyze_image(image_path, config):
    with open(image_path, "rb") as image_file:
        image_b64 = base64.b64encode(image_file.read()).decode()
    
    payload = {
        "model": config["ollama"]["vision_model"],
        "prompt": config["analysis_prompt"],
        "images": [image_b64],
        "stream": False
    }
    
    try:
        response = requests.post(
            config["ollama"]["api_url"],
            json=payload
        )
        return response.json()["response"]
    except Exception as e:
        print(f"Analysis failed: {str(e)}")
        return ""
