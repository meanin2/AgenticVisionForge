from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import yaml
import json
from datetime import datetime
import shutil

# Import orchestrator logic from existing code
from src.orchestrator import run_iterations

# This is your existing code that loads config; we can reuse or adapt it
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

app = Flask(__name__)

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'json', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    """Dashboard page showing recent runs and stats."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    
    # Get recent runs
    recent_runs = []
    if os.path.exists(runs_dir):
        runs = sorted(os.listdir(runs_dir), reverse=True)[:5]
        for run_name in runs:
            run_path = os.path.join(runs_dir, run_name)
            if os.path.isdir(run_path):
                # Get run details
                goal = None
                goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
                if os.path.exists(goal_analysis_path):
                    with open(goal_analysis_path, "r") as f:
                        data = json.load(f)
                        goal = data.get("goal")
                
                # Get number of iterations
                generations_path = os.path.join(run_path, "generations")
                num_iterations = len([f for f in os.listdir(generations_path) 
                                   if f.endswith('.png')]) if os.path.exists(generations_path) else 0
                
                recent_runs.append({
                    "name": run_name,
                    "goal": goal,
                    "iterations": num_iterations,
                    "timestamp": datetime.strptime(run_name.split("-")[0], "%Y%m%d").strftime("%Y-%m-%d")
                })
    
    return render_template("index.html", recent_runs=recent_runs)

@app.route("/generate", methods=["GET", "POST"])
def generate():
    """Handle image generation form and process."""
    if request.method == "POST":
        goal = request.form.get("goal", "").strip()
        max_iterations = request.form.get("max_iterations", "").strip()
        run_name = request.form.get("run_name", "").strip()
        output_dir = request.form.get("output_dir", "").strip()

        if not goal:
            return jsonify({"error": "Goal is required"}), 400

        config = load_config()

        if max_iterations:
            try:
                config["iterations"]["max_iterations"] = int(max_iterations)
            except ValueError:
                return jsonify({"error": "Invalid max iterations value"}), 400

        if output_dir:
            config["comfyui"]["output_dir"] = output_dir

        run_name = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        runs_dir = config.get("runs_directory", "runs")
        run_path = os.path.join(runs_dir, run_name)
        os.makedirs(run_path, exist_ok=True)

        try:
            run_iterations(config, goal, run_path)
            return jsonify({"redirect": url_for("results", run_name=run_name)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return render_template("generate.html")

@app.route("/gallery")
def gallery():
    """Display all generated images across all runs."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    
    runs = []
    if os.path.exists(runs_dir):
        for run_name in sorted(os.listdir(runs_dir), reverse=True):
            run_path = os.path.join(runs_dir, run_name)
            if os.path.isdir(run_path):
                generations_path = os.path.join(run_path, "generations")
                if os.path.exists(generations_path):
                    images = []
                    for img in sorted(os.listdir(generations_path)):
                        if img.endswith('.png'):
                            images.append({
                                "filename": img,
                                "path": f"/runs/{run_name}/generations/{img}"
                            })
                    if images:
                        # Get run details
                        goal = None
                        goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
                        if os.path.exists(goal_analysis_path):
                            with open(goal_analysis_path, "r") as f:
                                data = json.load(f)
                                goal = data.get("goal")
                        
                        runs.append({
                            "name": run_name,
                            "goal": goal,
                            "images": images
                        })
    
    return render_template("gallery.html", runs=runs)

@app.route("/workflows", methods=["GET", "POST"])
def workflows():
    """Manage ComfyUI workflows."""
    if request.method == "POST":
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and allowed_file(file.filename):
            filename = "comfyui_prompt_template.json"
            file.save(filename)
            return jsonify({"message": "Workflow uploaded successfully"})
        
        return jsonify({"error": "Invalid file type"}), 400
    
    # Check if workflow file exists
    workflow_exists = os.path.exists("comfyui_prompt_template.json")
    if workflow_exists:
        with open("comfyui_prompt_template.json", "r") as f:
            workflow_data = json.load(f)
    else:
        workflow_data = None
    
    return render_template("workflows.html", 
                         workflow_exists=workflow_exists,
                         workflow_data=workflow_data)

@app.route("/models")
def models():
    """Display and manage Ollama and Gemini models."""
    config = load_config()
    return render_template("models.html", config=config)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Configure application settings."""
    if request.method == "POST":
        try:
            config = {
                "runs_directory": request.form.get("runs_directory", "runs"),
                "iterations": {
                    "max_iterations": int(request.form.get("max_iterations", 10)),
                    "success_threshold": int(request.form.get("success_threshold", 90))
                },
                "comfyui": {
                    "api_url": request.form.get("comfyui_api_url", "http://localhost:8188"),
                    "output_dir": request.form.get("output_dir", "comfyui_outputs")
                },
                "vision": {
                    "provider": request.form.get("vision_provider", "gemini"),
                    "ollama": {
                        "model": request.form.get("vision_ollama_model", "llama3.2-vision"),
                        "api_url": request.form.get("vision_ollama_api_url", "http://localhost:11434/api/generate")
                    },
                    "gemini": {
                        "model": request.form.get("vision_gemini_model", "gemini-2.0-flash-exp"),
                        "api_key": request.form.get("vision_gemini_api_key", "")
                    }
                },
                "text": {
                    "provider": request.form.get("text_provider", "gemini"),
                    "ollama": {
                        "model": request.form.get("text_ollama_model", "deepseek-r1:8b"),
                        "api_url": request.form.get("text_ollama_api_url", "http://localhost:11434/api/generate"),
                        "strip_think_tags": request.form.get("strip_think_tags", "true") == "true"
                    },
                    "gemini": {
                        "model": request.form.get("text_gemini_model", "gemini-2.0-flash-exp"),
                        "api_key": request.form.get("text_gemini_api_key", "")
                    }
                }
            }
            
            with open("config.yaml", "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            return jsonify({"message": "Settings saved successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    config = load_config()
    return render_template("settings.html", config=config)

@app.route("/docs")
def docs():
    """Display documentation."""
    # Read README.md and convert to HTML (you might want to use a Markdown parser)
    with open("README.md", "r") as f:
        content = f.read()
    return render_template("docs.html", content=content)

@app.route("/results/<run_name>")
def results(run_name):
    """Display images and logs for a given run."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    generations_path = os.path.join(run_path, "generations")

    # Gather iteration images
    images = []
    if os.path.exists(generations_path):
        for filename in sorted(os.listdir(generations_path)):
            if filename.lower().endswith(".png") and filename.startswith("iteration_"):
                images.append(filename)

    # Gather iteration logs
    iteration_logs = []
    for filename in sorted(os.listdir(run_path)):
        if filename.startswith("iteration_") and filename.endswith(".json"):
            iteration_logs.append(filename)

    # Get goal and analysis
    goal = None
    analysis = None
    goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
    if os.path.exists(goal_analysis_path):
        with open(goal_analysis_path, "r") as f:
            data = json.load(f)
            goal = data.get("goal")
            analysis = data.get("analysis")

    return render_template("results.html", 
                         run_name=run_name,
                         images=images,
                         logs=iteration_logs,
                         goal=goal,
                         analysis=analysis)

@app.route("/runs/<run_name>/generations/<filename>")
def serve_generated_image(run_name, filename):
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name, "generations")
    return send_from_directory(run_path, filename)

@app.route("/runs/<run_name>/<filename>")
def serve_run_file(run_name, filename):
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    return send_from_directory(run_path, filename)

if __name__ == "__main__":
    # Run on an unconventional port, e.g. 6221
    # Use 0.0.0.0 so it is accessible from your network if desired
    app.run(port=6221, host="0.0.0.0", debug=True) 