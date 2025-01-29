from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import yaml
from datetime import datetime

# Import orchestrator logic from existing code
from src.orchestrator import run_iterations

# This is your existing code that loads config; we can reuse or adapt it
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    """
    Display a form where the user can input:
    - Goal
    - Max iterations (optional)
    - Run name (optional)
    - Output dir override (optional)
    """
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    """
    Handle form submission, run the iterative generation, 
    then redirect to a page that displays the results.
    """
    goal = request.form.get("goal", "").strip()
    max_iterations = request.form.get("max_iterations", "").strip()
    run_name = request.form.get("run_name", "").strip()
    output_dir = request.form.get("output_dir", "").strip()

    # Basic validation
    if not goal:
        return "Error: Goal is required.", 400

    # Load config
    config = load_config()

    # Apply optional overrides
    if max_iterations:
        try:
            config["iterations"]["max_iterations"] = int(max_iterations)
        except ValueError:
            pass

    if output_dir:
        config["comfyui"]["output_dir"] = output_dir

    # Generate a default run_name if not provided
    if not run_name:
        run_name = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Create run directory structure
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    os.makedirs(run_path, exist_ok=True)

    # Actually run the iterative process
    run_iterations(config, goal, run_path)

    # After finishing, redirect to a results page
    return redirect(url_for("results", run_name=run_name))

@app.route("/results/<run_name>")
def results(run_name):
    """
    Display images and logs for a given run.
    """
    # We'll show any PNG images from the generation directory
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

    return render_template("results.html", run_name=run_name, images=images, logs=iteration_logs)

# If you want to serve the actual images (PNG) directly:
@app.route("/runs/<run_name>/generations/<filename>")
def serve_generated_image(run_name, filename):
    config = load_config()
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name, "generations")
    return send_from_directory(run_path, filename)

# If you want to serve iteration logs
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