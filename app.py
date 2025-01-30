from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import yaml
import json
from datetime import datetime
import shutil

# Import orchestrator logic
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
    """Dashboard page showing recent runs and handling new generation requests."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    
    if request.method == "POST":
        try:
            goal = request.form.get("goal", "").strip()
            max_iterations = request.form.get("max_iterations", "").strip()
            run_name = request.form.get("run_name", "").strip()
            output_dir = request.form.get("output_dir", "").strip()

            if not goal:
                return jsonify({"error": "Goal is required"}), 400

            if max_iterations:
                try:
                    config["iterations"]["max_iterations"] = int(max_iterations)
                except ValueError:
                    return jsonify({"error": "Invalid max_iterations value"}), 400

            if output_dir:
                config["comfyui"]["output_dir"] = output_dir

            run_name = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
            run_path = os.path.join(runs_dir, run_name)
            os.makedirs(run_path, exist_ok=True)

            # Launch iteration process
            run_iterations(config, goal, run_path)

            # If successful, redirect to results
            return jsonify({"redirect": url_for("results", run_name=run_name)})

        except Exception as e:
            app.logger.exception("Error during new image generation:")
            return jsonify({"error": str(e)}), 500

    # GET request: show recent runs
    recent_runs = []
    if os.path.exists(runs_dir):
        # Only list the 5 most recent
        runs = sorted(os.listdir(runs_dir), reverse=True)[:5]
        for r in runs:
            run_path = os.path.join(runs_dir, r)
            if os.path.isdir(run_path):
                goal = None
                goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
                if os.path.exists(goal_analysis_path):
                    with open(goal_analysis_path, "r") as f:
                        data = json.load(f)
                        goal = data.get("goal")
                
                generations_path = os.path.join(run_path, "generations")
                num_iterations = 0
                if os.path.exists(generations_path):
                    num_iterations = len([f for f in os.listdir(generations_path) if f.endswith('.png')])

                # Parse date from run_name if it looks like YYYYMMDD-HHMMSS
                date_str = r.split("-")[0]
                try:
                    date_display = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                except ValueError:
                    date_display = r  # fallback if no parse

                recent_runs.append({
                    "name": r,
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

    images = []
    if os.path.exists(runs_dir):
        for run_name in sorted(os.listdir(runs_dir), reverse=True):
            run_path = os.path.join(runs_dir, run_name)
            if os.path.isdir(run_path):
                generations_path = os.path.join(run_path, "generations")
                if os.path.exists(generations_path):
                    for img in sorted(os.listdir(generations_path)):
                        if img.endswith('.png'):
                            images.append({
                                "url": f"/runs/{run_name}/generations/{img}",
                                "goal": run_name,
                                "date": run_name,
                            })
    return render_template("gallery.html", images=images)


@app.route("/workflows", methods=["GET", "POST"])
def workflows():
    """Manage ComfyUI workflows (upload, download, delete)."""
    if request.method == "POST":
        try:
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
        except Exception as e:
            app.logger.exception("Error uploading workflow:")
            return jsonify({"error": str(e)}), 500

    workflow_exists = os.path.exists("comfyui_prompt_template.json")
    workflow_data = None
    if workflow_exists:
        try:
            with open("comfyui_prompt_template.json", "r") as f:
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
        try:
            api_key = request.form.get("api_key", "")
            vision_model = request.form.get("vision_model", "")
            text_model = request.form.get("text_model", "")

            config["vision"]["gemini"]["api_key"] = api_key or config["vision"]["gemini"].get("api_key", "")
            if vision_model:
                config["vision"]["gemini"]["model"] = vision_model
            if text_model:
                config["text"]["gemini"]["model"] = text_model

            with open("config.yaml", "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False)

            return jsonify({"message": "Configuration saved successfully"})
        except Exception as e:
            app.logger.exception("Error saving model configuration:")
            return jsonify({"error": str(e)}), 500
    
    return render_template("models.html", config=config)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """
    Main settings route (mostly for GET).
    The actual saving logic is handled in /settings/general, /settings/advanced, etc.
    """
    if request.method == "POST":
        return jsonify({"message": "Settings updated (placeholder)"}), 200
    config = load_config()
    return render_template("settings.html", config=config)


@app.route("/settings/general", methods=["POST"])
def save_settings_general():
    """
    Example endpoint to save 'general' settings.
    Currently a placeholder; you’d implement real logic for your config here.
    """
    # For demonstration, we just return success.
    # In a real app, parse request.form, update config.yaml, etc.
    return jsonify({"message": "General settings saved"}), 200


@app.route("/settings/advanced", methods=["POST"])
def save_settings_advanced():
    """
    Example endpoint to save 'advanced' settings.
    """
    return jsonify({"message": "Advanced settings saved"}), 200


@app.route("/settings/reset", methods=["POST"])
def reset_settings():
    """
    Resets config.yaml to config.example.yaml if it exists.
    """
    if os.path.exists("config.example.yaml"):
        try:
            shutil.copy("config.example.yaml", "config.yaml")
            return jsonify({"message": "Settings have been reset to defaults"}), 200
        except Exception as e:
            app.logger.exception("Error resetting settings:")
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "No config.example.yaml found"}), 404


@app.route("/settings/clear-cache", methods=["POST"])
def clear_cache():
    """Placeholder for clearing caches."""
    return jsonify({"message": "Cache cleared (placeholder)"}), 200


@app.route("/docs")
def docs():
    """Display README.md content on a documentation page."""
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

    images = []
    if os.path.exists(generations_path):
        for filename in sorted(os.listdir(generations_path)):
            if filename.lower().endswith(".png") and filename.startswith("iteration_"):
                images.append(filename)

    iteration_logs = []
    for filename in sorted(os.listdir(run_path)):
        if filename.startswith("iteration_") and filename.endswith(".json"):
            iteration_logs.append(filename)

    goal = None
    analysis = None
    goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
    if os.path.exists(goal_analysis_path):
        with open(goal_analysis_path, "r") as f:
            data = json.load(f)
            goal = data.get("goal")
            analysis = data.get("analysis")

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
    """Get status of a generation run (images, logs, done?)."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    generations_path = os.path.join(run_path, "generations")

    images = []
    logs = []
    done = False

    if os.path.exists(generations_path):
        for filename in sorted(os.listdir(generations_path)):
            if filename.lower().endswith(".png") and filename.startswith("iteration_"):
                images.append(filename)

    for filename in sorted(os.listdir(run_path)):
        if filename.startswith("iteration_") and filename.endswith(".json"):
            logs.append(filename)

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
    """Delete an entire run directory."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    
    if not os.path.exists(run_path):
        return jsonify({"error": "Run not found"}), 404
    
    try:
        shutil.rmtree(run_path)
        return jsonify({"message": "Run deleted successfully"})
    except Exception as e:
        app.logger.exception("Error deleting run directory:")
        return jsonify({"error": f"Failed to delete run: {str(e)}"}), 500


@app.route("/runs/<run_name>/goal", methods=["POST"])
def edit_run_goal(run_name):
    """Update the goal mid-run."""
    data = request.get_json() or {}
    new_goal = data.get("goal")
    if not new_goal:
        return jsonify({"error": "No new goal provided"}), 400

    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    goal_analysis_path = os.path.join(run_path, "goal_analysis.json")

    if os.path.exists(run_path):
        ga_data = {}
        if os.path.exists(goal_analysis_path):
            with open(goal_analysis_path, "r") as f:
                ga_data = json.load(f)
        ga_data["goal"] = new_goal
        with open(goal_analysis_path, "w") as f:
            json.dump(ga_data, f, indent=2)
        return jsonify({"message": "Goal updated"})
    return jsonify({"error": "Run not found"}), 404


@app.route("/runs/<run_name>/cancel", methods=["POST"])
def cancel_run(run_name):
    """Mark a run as canceled by creating a canceled.txt file."""
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    if os.path.exists(run_path):
        with open(os.path.join(run_path, "canceled.txt"), "w") as f:
            f.write("Run was canceled.")
        return jsonify({"message": "Run canceled"})
    return jsonify({"error": "Run not found"}), 404


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


# ----------------------------------------------------------------
# New: Fixing placeholder for image deletion from gallery (API)
# ----------------------------------------------------------------
@app.route("/api/images/<image_id>", methods=["DELETE"])
def delete_image_api(image_id):
    """
    Attempt to find an image file named <image_id> in the 'generations'
    folder of any existing run and delete it. Returns 404 if not found.
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")

    found_file = None
    for run_name in os.listdir(runs_dir):
        gen_path = os.path.join(runs_dir, run_name, "generations")
        if os.path.isdir(gen_path):
            candidate = os.path.join(gen_path, image_id)
            if os.path.exists(candidate):
                found_file = candidate
                break

    if not found_file:
        return jsonify({"error": f"Image {image_id} not found"}), 404

    try:
        os.remove(found_file)
        return jsonify({"message": f"Image {image_id} deleted successfully."}), 200
    except Exception as e:
        app.logger.exception("Error deleting image file:")
        return jsonify({"error": f"Could not delete image: {str(e)}"}), 500


# ----------------------------------------------------------------
# New: Fixing placeholder /upload route for drag-and-drop uploads
# ----------------------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Handle file uploads via drag-and-drop or standard form.
    Allows JSON or PNG, stores them in 'uploads/' folder by default.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Allowed: .json, .png"}), 400

    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)

    save_path = os.path.join(uploads_dir, file.filename)
    try:
        file.save(save_path)
    except Exception as e:
        app.logger.exception("Error saving uploaded file:")
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    return jsonify({"message": "File uploaded successfully!"}), 200


if __name__ == "__main__":
    # Run on port 6221 (or any other). Debug enabled for development only.
    app.run(port=6221, host="0.0.0.0", debug=True)
