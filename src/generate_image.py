import json
import os
import uuid
import websocket
import urllib.request
import urllib.parse
from PIL import Image
import io
import random

def queue_prompt(prompt, server_address, client_id):
    """Queue a prompt for execution on the ComfyUI server."""
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type, server_address):
    """Get an image from the ComfyUI server."""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id, server_address):
    """Get the execution history for a prompt."""
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

def save_image_data(image_data, output_path):
    """Save binary image data to a file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image = Image.open(io.BytesIO(image_data))
    image.save(output_path)

def get_images(ws, prompt, server_address, client_id):
    """Get generated images using WebSocket API."""
    prompt_id = queue_prompt(prompt, server_address, client_id)['prompt_id']
    output_images = {}
    
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
        else:
            continue  # Skip binary preview data

    history = get_history(prompt_id, server_address)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(
                    image['filename'],
                    image['subfolder'],
                    image['type'],
                    server_address
                )
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images

def generate_random_seed():
    """Generate a random seed for image generation."""
    return random.randint(1, 1000000000)

def find_node_by_class(workflow, class_type):
    """Find the first node of a specific class type in the workflow."""
    for node_id, node in workflow.items():
        if node.get("class_type") == class_type:
            return node_id
    return None

def find_node_by_title(workflow, title):
    """Find a node by its title in the workflow."""
    for node_id, node in workflow.items():
        meta = node.get("_meta", {})
        if meta.get("title", "").lower() == title.lower():
            return node_id
    return None

def find_prompt_node(workflow):
    """
    Find the node containing the PROMPT_PLACEHOLDER.
    Returns (node_id, None) if found, or (None, error_message) if not found.
    """
    for node_id, node in workflow.items():
        if node.get("class_type") == "CLIPTextEncode":
            if node["inputs"].get("text") == "PROMPT_PLACEHOLDER":
                return node_id, None
    return None, "No CLIPTextEncode node with PROMPT_PLACEHOLDER found. Please set the text input to PROMPT_PLACEHOLDER in your workflow."

def find_seed_node(workflow):
    """
    Find the node that controls the random seed.
    Looks for:
    1. Node with 'RandomNoise' class type
    2. Node with 'Random' in title
    3. Node with 'noise_seed' in inputs
    """
    # Try by class type first
    node_id = find_node_by_class(workflow, "RandomNoise")
    if node_id:
        return node_id, None

    # Try by title containing "Random"
    for node_id, node in workflow.items():
        meta = node.get("_meta", {})
        if "random" in meta.get("title", "").lower():
            return node_id, None

    # Try by input parameter
    for node_id, node in workflow.items():
        if "noise_seed" in node.get("inputs", {}):
            return node_id, None

    return None, "No random seed node found. Please ensure your workflow has a RandomNoise node or a node with noise_seed input."

def generate_image(prompt_text, config, iteration):
    """
    Generate an image using ComfyUI's WebSocket API.
    Returns the path where the image was saved.
    """
    # Read the JSON workflow
    with open("comfyui_prompt_template.json", "r") as f:
        workflow = json.load(f)

    # Find required nodes
    prompt_node_id, prompt_error = find_prompt_node(workflow)
    if prompt_error:
        raise ValueError(prompt_error)

    save_node_id = find_node_by_class(workflow, "SaveImage")
    if not save_node_id:
        raise ValueError("No SaveImage node found in workflow")

    seed_node_id, seed_error = find_seed_node(workflow)
    if seed_error:
        raise ValueError(seed_error)

    # Insert user prompt
    workflow[prompt_node_id]["inputs"]["text"] = prompt_text
    # Set output filename
    workflow[save_node_id]["inputs"]["filename_prefix"] = f"iteration_{iteration}"
    # Set random seed
    if "noise_seed" in workflow[seed_node_id]["inputs"]:
        workflow[seed_node_id]["inputs"]["noise_seed"] = generate_random_seed()

    # Setup WebSocket connection
    server_address = config['comfyui']['api_url'].replace('http://', '')
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect(f"ws://{server_address}/ws?clientId={client_id}")

    try:
        # Generate and get images
        images = get_images(ws, workflow, server_address, client_id)
        
        # Find the output from the SaveImage node
        if save_node_id in images and images[save_node_id]:
            output_path = os.path.join(
                config["comfyui"]["output_dir"],
                f"iteration_{iteration}.png"
            )
            save_image_data(images[save_node_id][0], output_path)
            return output_path
        else:
            raise Exception("No image generated by SaveImage node")
    finally:
        ws.close()

    return None 