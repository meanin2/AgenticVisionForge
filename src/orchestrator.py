import os
import json
from datetime import datetime

from .generate_image import generate_image
from .evaluation import analyze_image
from .ollama_text_utils import refine_prompt, generate_text_ollama, generate_text_gemini

def understand_goal(goal, config):
    """
    Use the configured text model to understand the goal and generate an initial prompt.
    Returns the analysis and the initial prompt.
    """
    # Format the goal understanding prompt
    prompt = config["prompts"]["goal_understanding"].format(goal=goal)
    
    # Use the configured provider
    provider = config["text"]["provider"]
    if provider == "ollama":
        response = generate_text_ollama(prompt, config)
    elif provider == "gemini":
        response = generate_text_gemini(prompt, config)
    else:
        raise ValueError(f"Unsupported text provider: {provider}")
    
    # Extract the initial prompt (last line of the response)
    lines = response.strip().split('\n')
    analysis = '\n'.join(lines[:-1])
    initial_prompt = lines[-1]
    
    return analysis, initial_prompt

def run_iterations(config, goal, run_directory):
    """Main iteration loop for generating and refining images."""
    print("\n=== Understanding Goal ===")
    analysis, current_prompt = understand_goal(goal, config)
    print("Goal Analysis:")
    print(analysis)
    print(f"\nInitial Prompt: {current_prompt}")
    
    # Save goal analysis
    goal_analysis_path = os.path.join(run_directory, "goal_analysis.json")
    with open(goal_analysis_path, "w", encoding="utf-8") as f:
        json.dump({
            "goal": goal,
            "analysis": analysis,
            "initial_prompt": current_prompt,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    iteration = 0
    max_iters = config["iterations"]["max_iterations"]

    while iteration < max_iters:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")

        # 1) Generate image
        image_path = generate_image(current_prompt, config, iteration)
        print(f"Generated image: {image_path}")

        # 2) Analyze image with vision model
        # Format the analysis prompt with the goal
        config["analysis_prompt"] = config["prompts"]["analysis"].format(goal=goal)
        analysis = analyze_image(image_path, config)
        print(f"Analysis: {analysis}")

        # 3) Refine prompt
        new_prompt = refine_prompt(current_prompt, analysis, config)
        print(f"Refined prompt: {new_prompt}")

        # 4) Log iteration data
        log_data = {
            "iteration": iteration,
            "prompt_before": current_prompt,
            "analysis": analysis,
            "prompt_after": new_prompt,
            "image_path": image_path,
            "timestamp": datetime.now().isoformat()
        }

        # Save JSON log
        iteration_log_path = os.path.join(run_directory, f"iteration_{iteration}.json")
        with open(iteration_log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)

        # 5) Prepare next iteration
        current_prompt = new_prompt

    print("\nAll iterations completed.") 