import os
import json
from datetime import datetime
from .generate_image import generate_image
from .evaluation import analyze_image
from .ollama_utils import refine_prompt

def run_iterations(config, goal, run_directory):
    current_prompt = goal
    iteration = 0
    
    while iteration < config["iterations"]["max_iterations"]:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")
        
        # Generate image
        image_path = generate_image(current_prompt, config, iteration)
        
        # Analyze image
        analysis = analyze_image(image_path, config)
        print(f"Analysis: {analysis}")
        
        # Refine prompt
        current_prompt = refine_prompt(current_prompt, analysis)
        print(f"New prompt: {current_prompt}")
        
        # Save iteration data
        log_entry = {
            "iteration": iteration,
            "prompt": current_prompt,
            "image_path": image_path,
            "analysis": analysis
        }
        
        with open(f"{run_directory}/iteration_{iteration}.json", "w") as f:
            json.dump(log_entry, f, indent=2)
