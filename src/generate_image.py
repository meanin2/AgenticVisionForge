import json
import os
from urllib import request

def generate_image(prompt_text, config, iteration):
    # Load ComfyUI template
    with open("comfyui_prompt_template.json") as f:
        workflow = json.load(f)
    
    # Update prompt and output filename
    workflow["6"]["inputs"]["text"] = prompt_text
    workflow["9"]["inputs"]["filename_prefix"] = f"iteration_{iteration}"
    
    # Queue prompt
    data = json.dumps({"prompt": workflow}).encode()
    req = request.Request(
        f"{config['comfyui']['api_url']}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    # Execute and get image path
    with request.urlopen(req) as response:
        resp_data = json.loads(response.read())
        return os.path.join(
            config["comfyui"]["output_dir"],
            f"iteration_{iteration}.png"
        )
