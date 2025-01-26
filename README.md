# AgenticVisionForge: Iterative AI Image Refinement

**AgenticVisionForge** is a tool for refining AI-generated images through an iterative feedback loop. By combining **ComfyUI** for image generation with flexible AI models from **Ollama** (local inference) and **Gemini** (cloud-based API), the tool enables dynamic and customizable workflows for creating high-quality outputs.

---

## Key Features
- **ComfyUI Integration**: Generate images using a customizable ComfyUI workflow.
- **Vision Model Flexibility**: Use any vision model from Ollama or Gemini for image evaluation.
- **Text Model Flexibility**: Employ thinking models (e.g., DeepSeek R1) or standard text models for prompt refinement.
- **Mix-and-Match Models**: Combine Ollama and Gemini in any configuration for vision and text tasks.
- **Automated Feedback Loop**: Generate → Evaluate → Refine → Repeat until the desired quality is reached.
- **Advanced Handling of `<think>` Tags**: Automatically removes `<think>` tags from outputs of thinking models before sending prompts to ComfyUI.

---

## Prerequisites
1. **ComfyUI**:
   - Install and run locally. See the [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI) for details.
2. **Ollama** (optional):
   - Download and install from [Ollama](https://www.ollama.ai/). Start the server with:
     ```bash
     ollama serve
     ```
   - Download models such as `llama3.2-vision` or `DeepSeek R1`:
     ```bash
     ollama pull llama3.2-vision
     ollama pull deepseek-r1
     ```
3. **Gemini** (optional):
   - Obtain an API key from [AI Studio](https://aistudio.google.com/apikey).

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourname/agentic-vision-forge.git
   cd agentic-vision-forge
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

5. **Configure models**:
   - Ollama (if using): Ensure `ollama serve` is running and the required models are downloaded.
   - Gemini (if using): Set your API key in the configuration file.

---

## Configuration

### Workflow Setup
1. Open ComfyUI and design your workflow.
2. Export the workflow in **API format**.
3. Replace the contents of `comfyui_prompt_template.json` with your exported workflow.
   - Ensure your workflow includes placeholders like `"PROMPT_PLACEHOLDER"` for the input prompt.

### Configuration File
1. Copy `config.example.yaml` to `config.yaml`.
2. Customize the following options:
   - **ComfyUI Settings**:
     ```yaml
     comfyui:
       api_url: "http://localhost:8188"
       output_dir: "comfyui_outputs"
     ```
   - **Vision Models**:
     ```yaml
     vision:
       provider: "ollama"  # or "gemini"
       ollama:
         model: "llama3.2-vision"
         api_url: "http://localhost:11434/api/generate"
       gemini:
         model: "gemini-2.0-flash-exp"
         api_key: "YOUR_GEMINI_API_KEY"
     ```
   - **Text Models**:
     ```yaml
     text:
       provider: "ollama"  # or "gemini"
       ollama:
         model: "deepseek-r1"
         strip_think_tags: true
       gemini:
         model: "gemini-2.0-flash-exp"
     ```
   - **Iteration Settings**:
     ```yaml
     iterations:
       max_iterations: 10
       success_threshold: 90
     ```

### Setting Up Custom Workflows

You can use your own ComfyUI workflows with this tool. Here's how to set up a custom workflow:

1. **Design Your Workflow in ComfyUI**:
   - Build your workflow as normal in the ComfyUI interface
   - Make sure your workflow includes these essential nodes:
     - A `CLIPTextEncode` node for the prompt
     - A `SaveImage` node for output
     - A `RandomNoise` node (or any node with a `noise_seed` input)

2. **Prepare the Prompt Node**:
   - Find your `CLIPTextEncode` node
   - Set its text input to exactly: `PROMPT_PLACEHOLDER`
   - This is where the tool will insert generated prompts

3. **Export the Workflow**:
   - Click the "Save (API Format)" button in ComfyUI
   - This will download a JSON file
   - Copy the contents of this file to `comfyui_prompt_template.json`

4. **Verification**:
   The tool will automatically find the required nodes in your workflow by looking for:
   - Any `CLIPTextEncode` node containing `PROMPT_PLACEHOLDER`
   - Any `SaveImage` node for saving the output
   - A random seed node (identified by):
     - Class type `RandomNoise`, or
     - Title containing "Random", or
     - Any node with a `noise_seed` input

5. **Error Messages**:
   If your workflow is missing any required components, you'll see helpful error messages like:
   - "No CLIPTextEncode node with PROMPT_PLACEHOLDER found..."
   - "No SaveImage node found in workflow"
   - "No random seed node found..."

This flexible setup allows you to use any workflow structure as long as it includes these basic components. The tool will automatically adapt to your workflow's node IDs and configuration.

---

## Usage

Run the tool with your desired goal:
```bash
python main.py --goal "A futuristic cityscape with flying cars"
```

### Optional Arguments
- `--max_iterations`: Override the maximum iterations in `config.yaml`.
- `--run_name`: Specify a custom name for the run.
- `--output_dir`: Set a custom directory for output images and logs.

---

## Process Overview

1. **Input the Goal**: Provide a description of your desired image.
2. **Generate an Image**: ComfyUI uses the configured workflow to generate an image.
3. **Evaluate the Image**: A vision model analyzes the image and provides feedback.
4. **Refine the Prompt**: A text model refines the prompt based on feedback.
5. **Repeat**: The process continues until the success threshold or iteration limit is reached.

---

## Supported Models

### Vision Models
- Ollama: Any vision model, such as `llama3.2-vision`.
- Gemini: Models like `gemini-2.0-flash-exp`.

### Text Models
- Ollama: Use models like `DeepSeek R1` with `<think>` tag support.
- Gemini: Standard text models for prompt refinement.

---

## Troubleshooting

1. **Invalid Workflow**:
   - Ensure the workflow in `comfyui_prompt_template.json` is exported in **API format**.
2. **Connection Issues**:
   - Verify that ComfyUI and Ollama servers are running if configured.
   - Ensure the Gemini API key is set in `config.yaml`.
3. **No Output**:
   - Check if the output directory in `config.yaml` has the correct permissions.

---

## References
- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [Ollama](https://www.ollama.ai/)
- [Gemini API Key](https://aistudio.google.com/apikey)

---

## License
[MIT](LICENSE)
