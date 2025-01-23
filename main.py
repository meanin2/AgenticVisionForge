import argparse
import os
import yaml
from datetime import datetime
from src.orchestrator import run_iterations

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Iterative Image Generation System")
    parser.add_argument(
        "--goal", 
        type=str,
        required=True,
        help="Primary objective for image generation (e.g., 'A cyberpunk cityscape')"
    )
    parser.add_argument(
        "--run_name", 
        type=str,
        default=None,
        help="Custom name for this generation run (default: timestamp)"
    )
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=None,
        help="Override maximum number of iterations from config"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Custom output directory override"
    )
    return parser.parse_args()

def load_config():
    """Load configuration from YAML file"""
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def setup_directories(config, run_name):
    """Create directory structure for the run"""
    runs_dir = config.get("runs_directory", "runs")
    run_path = os.path.join(runs_dir, run_name)
    
    dirs_to_create = [
        run_path,
        os.path.join(run_path, "logs"),
        os.path.join(run_path, "generations"),
        os.path.join(run_path, "analyses")
    ]
    
    for dir_path in dirs_to_create:
        os.makedirs(dir_path, exist_ok=True)
        
    return run_path

def main():
    # Parse command-line arguments
    args = parse_arguments()
    
    # Load configuration
    config = load_config()
    
    # Apply command-line overrides
    if args.max_iterations:
        config["iterations"]["max_iterations"] = args.max_iterations
    if args.output_dir:
        config["comfyui"]["output_dir"] = args.output_dir
    
    # Create run identifier
    run_name = args.run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Set up directory structure
    run_directory = setup_directories(config, run_name)
    
    # Update config paths with run-specific directories
    config["comfyui"]["output_dir"] = os.path.join(run_directory, "generations")
    config["logs"]["directory"] = os.path.join(run_directory, "logs")
    
    # Start the iteration process
    run_iterations(config, args.goal, run_directory)

if __name__ == "__main__":
    main()
