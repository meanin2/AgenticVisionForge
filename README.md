# Iterative Image Refinement with ComfyUI + Ollama

This tool generates and refines images iteratively based on your input goal. It combines ComfyUI for image creation and Ollama for analysis and prompt refinement, creating a feedback loop to improve the final output.

## Key Features
- **ComfyUI Integration**: Generates images using your local ComfyUI setup.
- **Ollama Vision Model**: Evaluates images to check alignment with the goal.
- **Ollama Text Model**: Suggests refined prompts for better results.
- **Automatic Looping**: Iterates until the desired quality or max steps are achieved.

---

## Getting Started

### Installation
1. **Clone this repository**:
   ```bash
   git clone https://github.com/yourname/iterative-comfy-ollama.git
   cd iterative-comfy-ollama
   ```

2. **Set up a Python environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start ComfyUI**:
   ```bash
   cd /path/to/ComfyUI
   python main.py --port 8188
   ```

5. **Ensure Ollama is running**:
   ```bash
   ollama serve
   ollama pull llama3.2-vision
   ollama pull llama3
   ```

---

### How It Works

1. **Input your goal**: Provide a description of what you want (e.g., "A futuristic cityscape with flying cars").
2. **Generate images**: The tool uses a preconfigured ComfyUI workflow to generate an image.
3. **Evaluate and refine**: Images are analyzed by Ollama's vision model, and a refined prompt is generated.
4. **Repeat**: The process continues until the output meets your criteria or reaches the iteration limit.

---

### Usage

**Run the tool**:
```bash
python main.py --goal "Your description here"
```

**Options**:
- `--max_iterations`: Override the maximum iterations set in `config.yaml`.
- `--output_dir`: Set a custom directory for generated images and logs.
- `--run_name`: Specify a custom name for this run.

---

### Configuring Your Workflow

- The workflow is defined in `comfyui_prompt_template.json`.
- You can paste your own ComfyUI workflow into this file.  
  - **Ensure it is in API format** by exporting it from ComfyUI:
    1. Open ComfyUI.
    2. Load your workflow.
    3. Export it via **API**.
  - Replace `"PROMPT_PLACEHOLDER"` with your prompt dynamically during iterations.

---

### Files & Directories

- `comfyui_prompt_template.json`: Base workflow for image generation.
- `config.example.yaml`: Configuration template to set models, max iterations, and other options.
- `src/`: Core modules for image generation, evaluation, and orchestration.
- `runs/`: Directory where outputs and logs are saved for each run.

---

### Troubleshooting

1. **Invalid workflow error**:
   - Ensure `comfyui_prompt_template.json` matches the API format required by ComfyUI.

2. **Ollama connection issues**:
   - Verify `ollama serve` is running and models are downloaded.

3. **No output image**:
   - Check `config["comfyui"]["output_dir"]` and ensure it matches your permissions.

---

## License
[MIT](LICENSE)

Happy refining!
