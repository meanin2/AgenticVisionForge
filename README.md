# Iterative Text-to-Image with ComfyUI + Ollama

An iterative loop that:
1. Takes a user **goal** (e.g., "A futuristic cityscape with flying cars"),
2. Generates an **image** using ComfyUI,
3. Evaluates the image via **Ollama's vision model** to see how well it matches the goal,
4. Uses Ollama's **text model** to propose an improved prompt,
5. Repeats until a success threshold or max iterations is reached.

## Features
- **ComfyUI** Integration: Generate images via local ComfyUI server.
- **Ollama Vision**: Evaluate each image with an LLaVA-style vision model (e.g., `llama3.2-vision`).
- **Ollama Text**: Refine the prompt using a text model (e.g., `llama3` or `mistral`).
- **Iteration**: Loop until satisfied or max steps.

## Prerequisites
- **Python 3.8+**
- **ComfyUI** running locally on `http://localhost:8188`.
  - See [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI).
- **Ollama** running on `http://localhost:11434`.  
  - Download and load the relevant models:
    ```bash
    ollama pull llama3.2-vision
    ollama pull llama3
    ```
- (Optional) GPU with sufficient VRAM for stable diffusion.

## Installation
1. **Clone** this repo:
   ```bash
   git clone https://github.com/yourname/my-iterative-comfy-ollama.git
   cd my-iterative-comfy-ollama
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Start ComfyUI** (in a separate terminal):
   ```bash
   cd /path/to/ComfyUI
   python main.py --port 8188
   ```
5. **Ensure Ollama** is running (default port 11434):
   ```bash
   # For example on macOS:
   brew tap jmorganca/ollama
   brew install ollama
   ollama serve
   # Then pull the needed models:
   ollama pull llama3.2-vision
   ollama pull llama3
   ```

## Usage
**Basic example**:
```bash
python main.py --goal "A futuristic cityscape with flying cars"
```
This will:
1. Create a run directory under `runs/`.
2. Generate `iteration_1.png`.
3. Evaluate it with `llama3.2-vision`.
4. Refine the prompt with `llama3`.
5. Repeat.

**Configurable Options**:
- Edit `config.yaml` to change:
  - `ollama.vision_model` / `ollama.text_model`
  - `iterations.max_iterations`
  - `iterations.success_threshold`
  - etc.

**Thinking Tags**:
If you're using a text-only model that outputs `<think>...</think>` before the actual response, set:
```yaml
ollama:
  strip_think_tags: true
```
in `config.yaml`. The system will strip out those tags so only the final user-facing text remains.

## Files & Directories
- `comfyui_prompt_template.json`: The base ComfyUI workflow (valid JSON with "negative" node).
- `src/generate_image.py`: Submits the JSON to ComfyUI's `POST /prompt` endpoint.
- `src/evaluation.py`: Sends the resulting PNG to Ollama's vision model.
- `src/ollama_text_utils.py`: Uses Ollama's text model to refine the prompt, optionally stripping `<think>` tags.
- `src/orchestrator.py`: Main loop. Each iteration: generate → evaluate → refine → loop.

## Troubleshooting
- **HTTP 400 from ComfyUI**:
  - Usually means the prompt JSON references a non-existent node or the workflow is invalid. 
  - Ensure `comfyui_prompt_template.json` has a matching negative-prompt node if used.
- **Ollama not connecting**:
  - Check that `ollama serve` is running on port 11434.
- **Image not found**:
  - Ensure you have correct permissions and the path in `config["comfyui"]["output_dir"]` matches.

## License
[MIT](LICENSE)

Happy iterating! 