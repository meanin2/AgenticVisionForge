import argparse
import os
import yaml
from datetime import datetime
from src.orchestrator import run_iterations
from src.utils import load_env_vars, replace_env_vars

def parse_arguments():
    parser = argparse.ArgumentParser(description="Iterative Image Generation with ComfyUI + Ollama")
    parser.add_argument("--goal", type=str, required=True,
                        help="Describe the image you want to generate")
    parser.add_argument("--run_name", type=str,
                        help="Optional custom run directory name")
    parser.add_argument("--max_iterations", type=int,
                        help="Override max_iterations from config.yaml")
    parser.add_argument("--output_dir", type=str,
                        help="Override comfyui output_dir from config.yaml")
    return parser.parse_args()

def load_config():
    # First load environment variables
    load_env_vars()
    
    # Then load and process config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables in config
    return replace_env_vars(config)

def setup_directories(config, run_name):
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)

    os.makedirs(run_path, exist_ok=True)
    os.makedirs(os.path.join(run_path, "logs"), exist_ok=True)
    os.makedirs(os.path.join(run_path, "generations"), exist_ok=True)
    os.makedirs(os.path.join(run_path, "analyses"), exist_ok=True)

    return run_path

def main():
    args = parse_arguments()
    config = load_config()

    # Apply CLI overrides
    if args.max_iterations is not None:
        config["iterations"]["max_iterations"] = args.max_iterations
    if args.output_dir is not None:
        config["comfyui"]["output_dir"] = args.output_dir

    run_name = args.run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_directory = setup_directories(config, run_name)

    # Update config for this run
    config["comfyui"]["output_dir"] = os.path.join(run_directory, "generations")
    config["logs"]["directory"] = os.path.join(run_directory, "logs")

    run_iterations(config, args.goal, run_directory)

if __name__ == "__main__":
    main() 