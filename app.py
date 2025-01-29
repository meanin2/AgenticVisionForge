from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import yaml
import json
from datetime import datetime
import shutil

# Import orchestrator logic from existing code
from src.orchestrator import run_iterations

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

app = Flask(__name__)

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'json', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def index():
    """Dashboard page showing recent runs and stats."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    
    # Handle POST request for generation
    if request.method == "POST":
        # Debug: Log request details
        print("\nRequest Debug Info:")
        print("Content-Type:", request.headers.get('Content-Type'))
        print("Form Data:", request.form)
        print("Files:", request.files)
        
        goal = request.form.get("goal", "").strip()
        max_iterations = request.form.get("max_iterations", "").strip()
        run_name = request.form.get("run_name", "").strip()
        output_dir = request.form.get("output_dir", "").strip()

        # Debug: Log parsed values
        print("\nParsed Values:")
        print("Goal:", repr(goal))
        print("Max Iterations:", repr(max_iterations))
        print("Run Name:", repr(run_name))
        print("Output Dir:", repr(output_dir))

        if not goal:
            return jsonify({"error": "Goal is required"}), 400

        if max_iterations:
            try:
                config["iterations"]["max_iterations"] = int(max_iterations)
            except ValueError:
                return jsonify({"error": "Invalid max iterations value"}), 400

        if output_dir:
            config["comfyui"]["output_dir"] = output_dir

        run_name = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        run_path = os.path.join(runs_dir, run_name)
        os.makedirs(run_path, exist_ok=True)

        try:
            run_iterations(config, goal, run_path)
            # After successful generation, redirect to results
            return jsonify({"redirect": url_for("results", run_name=run_name)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # Get recent runs for display
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
                
                # Parse date from run_name if possible
                # e.g. run_name = 20240101-123456
                date_str = run_name.split("-")[0]
                try:
                    date_display = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                except ValueError:
                    date_display = run_name  # fallback
                
                recent_runs.append({
                    "name": run_name,
                    "goal": goal,
                    "iterations": num_iterations,
                    "timestamp": date_display
                })
    
    return render_template("index.html", recent_runs=recent_runs)

@app.route("/gallery")
def gallery():
    """Display all generated images across all runs."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    
    # Instead of passing runs, build a single list of images
    images = []
    if os.path.exists(runs_dir):
        for run_name in sorted(os.listdir(runs_dir), reverse=True):
            run_path = os.path.join(runs_dir, run_name)
            if os.path.isdir(run_path):
                generations_path = os.path.join(run_path, "generations")
                if os.path.exists(generations_path):
                    for img in sorted(os.listdir(generations_path)):
                        if img.endswith('.png'):
                            # (Optional) read the goal from goal_analysis.json if you want
                            # For now, just store run_name as "goal"
                            images.append({
                                "url": f"/runs/{run_name}/generations/{img}",
                                "goal": run_name,
                                "date": run_name,
                            })
    
    return render_template("gallery.html", images=images)

@app.route("/workflows", methods=["GET", "POST"])
def workflows():
    """Manage ComfyUI workflows."""
    if request.method == "POST":
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and allowed_file(file.filename) and file.filename.lower().endswith('.json'):
            filename = "comfyui_prompt_template.json"
            file.save(filename)
            return jsonify({"message": "Workflow uploaded successfully"})
        
        return jsonify({"error": "Invalid file type (must be JSON)"}), 400
    
    # Check if workflow file exists
    workflow_exists = os.path.exists("comfyui_prompt_template.json")
    workflow_data = None
    if workflow_exists:
        with open("comfyui_prompt_template.json", "r") as f:
            try:
                workflow_data = json.load(f)
            except json.JSONDecodeError:
                workflow_data = {}
    
    return render_template(
        "workflows.html", 
        workflow_exists=workflow_exists,
        workflow_data=workflow_data
    )

@app.route("/workflows/download", methods=["GET"])
def download_workflow():
    """Download the current workflow JSON file."""
    filename = "comfyui_prompt_template.json"
    if not os.path.exists(filename):
        return jsonify({"error": "No workflow file found"}), 404
    return send_from_directory('.', filename, as_attachment=True)

@app.route("/workflows/delete", methods=["POST"])
def delete_workflow():
    """Delete the current workflow JSON file."""
    filename = "comfyui_prompt_template.json"
    if os.path.exists(filename):
        os.remove(filename)
        return jsonify({"message": "Workflow deleted"})
    return jsonify({"error": "No workflow file to delete"}), 404

@app.route("/models", methods=["GET", "POST"])
def models():
    """Display and manage Ollama and Gemini models."""
    config = load_config()
    if request.method == "POST":
        # In the HTML, we will add name="api_key", name="vision_model", etc.
        # This is a minimal approach to storing them in config.yaml
        api_key = request.form.get("api_key", "")
        vision_model = request.form.get("vision_model", "")
        text_model = request.form.get("text_model", "")

        # Update config with these values
        config["vision"]["gemini"]["api_key"] = api_key or config["vision"]["gemini"].get("api_key", "")
        # If they choose a model from a dropdown
        if vision_model:
            config["vision"]["gemini"]["model"] = vision_model
        if text_model:
            config["text"]["gemini"]["model"] = text_model

        # Save
        with open("config.yaml", "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        
        return jsonify({"message": "Configuration saved successfully"})
    
    return render_template("models.html", config=config)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Configure application settings (Legacy single-route)."""
    # We keep it for backward-compat in the UI or for GET:
    if request.method == "POST":
        # If you want, handle everything here
        # This is a placeholder because the templates call separate endpoints
        return jsonify({"message": "Settings updated (via POST /settings) - not fully implemented here"})
    config = load_config()
    return render_template("settings.html", config=config)

# Additional endpoints for the separate forms:

@app.route("/settings/general", methods=["POST"])
def save_settings_general():
    # Minimal placeholder
    # Parse form data
    # For example, request.form.get("whatever")
    return jsonify({"message": "General settings saved (placeholder)"})

@app.route("/settings/advanced", methods=["POST"])
def save_settings_advanced():
    return jsonify({"message": "Advanced settings saved (placeholder)"})

@app.route("/settings/reset", methods=["POST"])
def reset_settings():
    # As a placeholder, you might copy config.example.yaml => config.yaml
    if os.path.exists("config.example.yaml"):
        shutil.copy("config.example.yaml", "config.yaml")
        return jsonify({"message": "Settings have been reset to defaults"})
    return jsonify({"error": "No config.example.yaml found"}), 404

@app.route("/settings/clear-cache", methods=["POST"])
def clear_cache():
    # Placeholder for clearing caches
    return jsonify({"message": "Cache cleared (placeholder)"})

@app.route("/docs")
def docs():
    """Display documentation."""
    # Read README.md and convert to HTML (you might want to use a Markdown parser)
    with open("README.md", "r", encoding="utf-8") as f:
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

    # Pass max_iterations so results.html can display it
    max_iters = config["iterations"].get("max_iterations", 10)

    return render_template(
        "results.html", 
        run_name=run_name,
        images=images,
        logs=iteration_logs,
        goal=goal,
        analysis=analysis,
        max_iterations=max_iters
    )

@app.route("/results/<run_name>/status")
def results_status(run_name):
    """Get the current status of a generation run, including images and logs."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    generations_path = os.path.join(run_path, "generations")

    images = []
    logs = []
    done = False

    # Gather images
    if os.path.exists(generations_path):
        for filename in sorted(os.listdir(generations_path)):
            if filename.lower().endswith(".png") and filename.startswith("iteration_"):
                images.append(filename)

    # Gather iteration logs
    for filename in sorted(os.listdir(run_path)):
        if filename.startswith("iteration_") and filename.endswith(".json"):
            logs.append(filename)

    # Decide if "done"
    # Check if max iterations reached or if canceled
    max_iters = config["iterations"].get("max_iterations", 10)
    if len(images) >= max_iters:
        done = True
    if os.path.exists(os.path.join(run_path, "canceled.txt")):
        done = True

    return jsonify({
        "images": images,
        "logs": logs,
        "done": done
    })

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

@app.route("/runs/<run_name>/delete", methods=["POST"])
def delete_run(run_name):
    """Delete a run and all its associated files."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    
    if not os.path.exists(run_path):
        return jsonify({"error": "Run not found"}), 404
    
    try:
        # Delete the entire run directory and its contents
        shutil.rmtree(run_path)
        return jsonify({"message": "Run deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete run: {str(e)}"}), 500

# -------------------------
# Additional "runs" routes from the front end references:
# Edit run goal
@app.route("/runs/<run_name>/goal", methods=["POST"])
def edit_run_goal(run_name):
    """Update the goal mid-run (placeholder)."""
    data = request.get_json() or {}
    new_goal = data.get("goal")
    if not new_goal:
        return jsonify({"error": "No new goal provided"}), 400

    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
    if os.path.exists(run_path):
        # Update the goal_analysis.json
        ga_data = {}
        if os.path.exists(goal_analysis_path):
            with open(goal_analysis_path, "r") as f:
                ga_data = json.load(f)
        ga_data["goal"] = new_goal
        with open(goal_analysis_path, "w") as f:
            json.dump(ga_data, f, indent=2)
        return jsonify({"message": "Goal updated"})
    return jsonify({"error": "Run not found"}), 404

# Cancel run
@app.route("/runs/<run_name>/cancel", methods=["POST"])
def cancel_run(run_name):
    """Placeholder for canceling a run. You might set a status in a file or DB."""
    # Minimal approach: create a canceled.txt or something
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    if os.path.exists(run_path):
        with open(os.path.join(run_path, "canceled.txt"), "w") as f:
            f.write("Run was canceled.")
        return jsonify({"message": "Run canceled"})
    return jsonify({"error": "Run not found"}), 404

# Get iteration prompt
@app.route("/runs/<run_name>/iterations/<int:iteration>/prompt", methods=["GET"])
def get_iteration_prompt(run_name, iteration):
    """
    Return the prompt used in iteration_<iteration>.json
    so the front-end can "View Prompt".
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    iteration_log_path = os.path.join(run_path, f"iteration_{iteration}.json")
    if not os.path.exists(iteration_log_path):
        return jsonify({"error": "Iteration log not found"}), 404

    with open(iteration_log_path, "r") as f:
        data = json.load(f)
    prompt = data.get("prompt", "")
    return jsonify({"prompt": prompt})

# -------------------------
# Placeholder route for image deletion from gallery:
@app.route("/api/images/<image_id>", methods=["DELETE"])
def delete_image_api(image_id):
    """
    We do not have an actual ID system for images.
    This is just a placeholder that always returns success.
    """
    return jsonify({"message": f"Image {image_id} deleted (placeholder)"}), 200

if __name__ == "__main__":
    # Run on an unconventional port, e.g. 6221
    # Use 0.0.0.0 so it is accessible from your network if desired
    app.run(port=6221, host="0.0.0.0", debug=True)
