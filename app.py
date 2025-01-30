import os
import yaml
import json
import shutil
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from src.orchestrator import run_iterations

app = Flask(__name__)

# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

ALLOWED_EXTENSIONS = {'json', 'png'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------------------------------------------------------
# Index & Basic Dashboard
# ----------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """
    Display the main dashboard page (recent runs).
    Now only handles GET for listing runs. The generation
    POST logic is moved to /create_run.
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")

    recent_runs = []
    if os.path.exists(runs_dir):
        runs = sorted(os.listdir(runs_dir), reverse=True)[:5]
        for run_name in runs:
            run_path = os.path.join(runs_dir, run_name)
            if os.path.isdir(run_path):
                # Load goal if present
                goal = None
                goal_analysis_path = os.path.join(run_path, "goal_analysis.json")
                if os.path.exists(goal_analysis_path):
                    with open(goal_analysis_path, "r") as f:
                        data = json.load(f)
                        goal = data.get("goal")
                
                # Count iterations
                generations_path = os.path.join(run_path, "generations")
                num_iterations = 0
                if os.path.exists(generations_path):
                    num_iterations = sum(1 for f in os.listdir(generations_path) if f.endswith('.png'))

                # Attempt to parse date from run_name
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


# ----------------------------------------------------------------
# New Route: /create_run (POST) 
# Quickly creates a run and returns run_name
# ----------------------------------------------------------------

@app.route("/create_run", methods=["POST"])
def create_run():
    """
    Receives the form data for generating an image. Instead of blocking
    the request with run_iterations, it simply:

    1. Creates a run directory
    2. Merges config with user-provided overrides (goal, max_iterations, etc.)
    3. Saves a config_dump.json in the run directory
    4. Returns { run_name: ... }

    The actual generation is triggered separately with /start_run/<run_name>.
    """
    try:
        config = load_config()
        runs_dir = config.get("runs_directory", "runs")

        # Parse form
        goal = request.form.get("goal", "").strip()
        if not goal:
            return jsonify({"error": "Goal is required"}), 400

        max_iterations = request.form.get("max_iterations", "").strip()
        run_name = request.form.get("run_name", "").strip() or datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = request.form.get("output_dir", "").strip()

        # Apply overrides
        if max_iterations:
            try:
                config["iterations"]["max_iterations"] = int(max_iterations)
            except ValueError:
                return jsonify({"error": "Invalid max_iterations value"}), 400

        if output_dir:
            config["comfyui"]["output_dir"] = output_dir

        # Create run directory
        run_path = os.path.join(runs_dir, run_name)
        os.makedirs(run_path, exist_ok=True)
        os.makedirs(os.path.join(run_path, "generations"), exist_ok=True)

        # Save the relevant user input + config in run_path
        # We'll read it in /start_run/<run_name>.
        user_data = {
            "goal": goal,
            "config": config
        }
        with open(os.path.join(run_path, "config_dump.json"), "w") as f:
            json.dump(user_data, f, indent=2)

        return jsonify({"run_name": run_name}), 200

    except Exception as e:
        app.logger.exception("Error creating new run:")
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------
# New Route: /start_run/<run_name> (POST)
# Actually starts the generation in a background thread
# ----------------------------------------------------------------

def background_run_iterations(run_path):
    """
    This function runs in a thread to call run_iterations
    with the stored config and goal from config_dump.json
    """
    try:
        with open(os.path.join(run_path, "config_dump.json"), "r") as f:
            data = json.load(f)
        goal = data["goal"]
        config = data["config"]
        # Mark as started
        started_flag = os.path.join(run_path, "started.txt")
        with open(started_flag, "w") as f:
            f.write("Run started.")

        # Actually run the iterative process
        run_iterations(config, goal, run_path)

    except Exception as e:
        app.logger.exception("Error in background_run_iterations:")

@app.route("/start_run/<run_name>", methods=["POST"])
def start_run(run_name):
    """
    If not already started, spawn a thread to run_iterations. 
    Returns JSON success immediately.
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)

    if not os.path.exists(run_path):
        return jsonify({"error": "Run not found"}), 404

    # Check if already started
    started_flag = os.path.join(run_path, "started.txt")
    if os.path.exists(started_flag):
        return jsonify({"message": "Run already started"}), 200

    # Spawn a background thread
    thread = threading.Thread(target=background_run_iterations, args=(run_path,))
    thread.daemon = True
    thread.start()

    return jsonify({"message": f"Run '{run_name}' started"}), 200


# ----------------------------------------------------------------
# Results / Status
# ----------------------------------------------------------------

@app.route("/results/<run_name>")
def results(run_name):
    """
    Display images and logs for a given run.
    The page polls /results/<run_name>/status for updates,
    and also calls /start_run/<run_name> if the run isn't started.
    """
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

    max_iters = 10
    # If the config is in config_dump.json, we can read to see if the user override is set
    config_dump = os.path.join(run_path, "config_dump.json")
    if os.path.exists(config_dump):
        with open(config_dump, "r") as f:
            cd = json.load(f)
            max_iters = cd["config"]["iterations"].get("max_iterations", 10)

    return render_template("results.html",
                           run_name=run_name,
                           images=images,
                           logs=iteration_logs,
                           goal=goal,
                           analysis=analysis,
                           max_iterations=max_iters)


@app.route("/results/<run_name>/status")
def results_status(run_name):
    """
    Returns a JSON with the current images, logs, if done, and if started.
    The front-end uses this for polling updates.
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    generations_path = os.path.join(run_path, "generations")

    if not os.path.exists(run_path):
        return jsonify({"error": "Run not found"}), 404

    images = []
    logs = []
    done = False
    started = False

    if os.path.exists(generations_path):
        for filename in sorted(os.listdir(generations_path)):
            if filename.lower().endswith(".png") and filename.startswith("iteration_"):
                images.append(filename)

    for filename in sorted(os.listdir(run_path)):
        if filename.startswith("iteration_") and filename.endswith(".json"):
            logs.append(filename)

    # Check if started
    started_flag = os.path.join(run_path, "started.txt")
    if os.path.exists(started_flag):
        started = True

    # Decide if done
    #   1) If we reached max_iterations
    #   2) If canceled.txt is present
    max_iters = config["iterations"].get("max_iterations", 10)
    config_dump = os.path.join(run_path, "config_dump.json")
    if os.path.exists(config_dump):
        with open(config_dump, "r") as f:
            cd = json.load(f)
        max_iters = cd["config"]["iterations"].get("max_iterations", 10)

    if len(images) >= max_iters:
        done = True
    if os.path.exists(os.path.join(run_path, "canceled.txt")):
        done = True

    return jsonify({
        "images": images,
        "logs": logs,
        "done": done,
        "started": started
    })


# ----------------------------------------------------------------
# Serving Generated Images, Logs, and Deletion
# ----------------------------------------------------------------

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

# Cancel mid-run
@app.route("/runs/<run_name>/cancel", methods=["POST"])
def cancel_run(run_name):
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    if os.path.exists(run_path):
        with open(os.path.join(run_path, "canceled.txt"), "w") as f:
            f.write("Run was canceled.")
        return jsonify({"message": "Run canceled"})
    return jsonify({"error": "Run not found"}), 404

# Edit run goal
@app.route("/runs/<run_name>/goal", methods=["POST"])
def edit_run_goal(run_name):
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


# ----------------------------------------------------------------
# Models, Workflows, Settings, etc. (unchanged from prior except placeholders)
# ----------------------------------------------------------------

@app.route("/models", methods=["GET", "POST"])
def models():
    try:
        config = load_config()
        if request.method == "POST":
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
        else:
            return render_template("models.html", config=config)
    except Exception as e:
        app.logger.exception("Error in /models:")
        return jsonify({"error": str(e)}), 500


@app.route("/workflows", methods=["GET", "POST"])
def workflows():
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
    
    return render_template("workflows.html",
                           workflow_exists=workflow_exists,
                           workflow_data=workflow_data)


@app.route("/workflows/download", methods=["GET"])
def download_workflow():
    filename = "comfyui_prompt_template.json"
    if not os.path.exists(filename):
        return jsonify({"error": "No workflow file found"}), 404
    return send_from_directory('.', filename, as_attachment=True)

@app.route("/workflows/delete", methods=["POST"])
def delete_workflow():
    filename = "comfyui_prompt_template.json"
    if os.path.exists(filename):
        os.remove(filename)
        return jsonify({"message": "Workflow deleted"})
    return jsonify({"error": "No workflow file to delete"}), 404


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        return jsonify({"message": "Settings updated (placeholder)"}), 200
    config = load_config()
    return render_template("settings.html", config=config)

@app.route("/settings/general", methods=["POST"])
def save_settings_general():
    return jsonify({"message": "General settings saved"}), 200

@app.route("/settings/advanced", methods=["POST"])
def save_settings_advanced():
    return jsonify({"message": "Advanced settings saved"}), 200

@app.route("/settings/reset", methods=["POST"])
def reset_settings():
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
    return jsonify({"message": "Cache cleared (placeholder)"}), 200


@app.route("/docs")
def docs():
    if not os.path.exists("README.md"):
        return "README.md not found.", 404
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()
    return render_template("docs.html", content=content)


# ----------------------------------------------------------------
# Image Deletion API
# ----------------------------------------------------------------

@app.route("/api/images/<image_id>", methods=["DELETE"])
def delete_image_api(image_id):
    """
    Searches all runs for an image named <image_id>
    in the 'generations' folder and deletes it.
    """
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")

    found_file = None
    for run_dir in os.listdir(runs_dir):
        gen_path = os.path.join(runs_dir, run_dir, "generations")
        if os.path.isdir(gen_path):
            candidate = os.path.join(gen_path, image_id)
            if os.path.exists(candidate):
                found_file = candidate
                break

    if not found_file:
        return jsonify({"error": f"Image {image_id} not found"}), 404

    try:
        os.remove(found_file)
        return jsonify({"message": f"Image {image_id} deleted successfully"}), 200
    except Exception as e:
        app.logger.exception("Error deleting image file:")
        return jsonify({"error": f"Could not delete image: {str(e)}"}), 500


# ----------------------------------------------------------------
# Upload Endpoint (for drag-and-drop)
# ----------------------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)

    save_path = os.path.join(uploads_dir, file.filename)
    try:
        file.save(save_path)
    except Exception as e:
        app.logger.exception("Error saving uploaded file:")
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    return jsonify({"message": "File uploaded successfully!"}), 200


# ----------------------------------------------------------------
# Run the Flask app
# ----------------------------------------------------------------

if __name__ == "__main__":
    app.run(port=6221, host="0.0.0.0", debug=True)
