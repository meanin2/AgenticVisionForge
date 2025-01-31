import os
import json
from datetime import datetime
import difflib

from .generate_image import generate_image
from .evaluation import analyze_image
from .ollama_text_utils import (
    understand_goal,
    create_initial_prompt,
    refine_prompt,
    extract_prompt_tags
)

def calculate_prompt_similarity(prompt1, prompt2):
    """Calculate how similar two prompts are using difflib."""
    return difflib.SequenceMatcher(None, prompt1, prompt2).ratio()

def evaluate_quality(analysis, current_prompt, previous_prompt, config, iteration, previous_analyses=None):
    """
    Evaluate the quality of the current iteration and decide whether to continue.
    Returns (should_continue, reason)
    """
    if previous_analyses is None:
        previous_analyses = []

    # Simplified logic if you want (this is just a placeholder).
    # For demonstration, we always continue up to max_iterations in this code.
    return True, "Continuing"

def run_iterations(config, goal, run_directory, progress_callback=None):
    """Main iteration loop for generating and refining images."""
    if progress_callback:
        progress_callback({
            'stage': 'setup',
            'message': 'Setting up generation...',
            'progress': 0
        })
    
    print("\n=== Understanding Goal ===")
    
    # Set up directories
    generations_dir = os.path.join(run_directory, "generations")
    os.makedirs(generations_dir, exist_ok=True)
    
    # Update config to use the generations directory
    config["comfyui"]["output_dir"] = generations_dir
    
    # 1. Initial goal analysis
    if progress_callback:
        progress_callback({
            'stage': 'analysis',
            'message': 'Analyzing goal...',
            'progress': 5
        })

    analysis_dict = understand_goal(goal, config)
    analysis_text = analysis_dict["response"]
    print("Goal Analysis:")
    print(analysis_text)

    # 2. Create initial T5 prompt
    if progress_callback:
        progress_callback({
            'stage': 'prompt',
            'message': 'Creating initial prompt...',
            'progress': 10
        })

    initial_prompt_dict = create_initial_prompt(goal, analysis_text, config)
    raw_initial_response = initial_prompt_dict["response"]
    # Extract the actual <prompt>...</prompt> content
    initial_prompt_text = extract_prompt_tags(raw_initial_response)
    if not initial_prompt_text:
        initial_prompt_text = raw_initial_response.strip()

    # Save iteration_0 with text interactions
    iteration_0_data = {
        "iteration": 0,
        "goal": goal,
        "text_interactions": [
            {
                "stage": "understand_goal",
                "system_prompt": analysis_dict["system_prompt"],
                "user_prompt": analysis_dict["user_prompt"],
                "response": analysis_dict["response"]
            },
            {
                "stage": "create_initial_prompt",
                "system_prompt": initial_prompt_dict["system_prompt"],
                "user_prompt": initial_prompt_dict["user_prompt"],
                "response": initial_prompt_dict["response"]
            }
        ],
        "timestamp": datetime.now().isoformat()
    }
    iteration_0_path = os.path.join(run_directory, "iteration_0.json")
    with open(iteration_0_path, "w", encoding="utf-8") as f:
        json.dump(iteration_0_data, f, indent=2)

    # Save a simpler goal_analysis.json for the UI
    goal_analysis_path = os.path.join(run_directory, "goal_analysis.json")
    with open(goal_analysis_path, "w", encoding="utf-8") as f:
        json.dump({
            "goal": goal,
            "analysis": analysis_text,
            "initial_prompt": initial_prompt_text,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    iteration = 0
    max_iters = config["iterations"]["max_iterations"]
    previous_prompt = None

    current_prompt = initial_prompt_text

    while iteration < max_iters:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")

        if progress_callback:
            progress_callback({
                'stage': 'generation',
                'message': f'Generating image {iteration}/{max_iters}...',
                'progress': 10 + (iteration * 90 / max_iters),
                'iteration': iteration,
                'max_iterations': max_iters
            })

        # 1) Generate image
        image_path = generate_image(current_prompt, config, iteration)
        print(f"Generated image: {image_path}")

        if progress_callback:
            progress_callback({
                'stage': 'analysis',
                'message': f'Analyzing image {iteration}/{max_iters}...',
                'progress': 10 + (iteration * 90 / max_iters),
                'iteration': iteration,
                'max_iterations': max_iters,
                'current_image': image_path
            })

        # 2) Unbiased description
        config['current_goal'] = goal
        describe_dict = analyze_image(image_path, config, stage="describe")
        image_description = describe_dict["response"]
        print(f"Image Description: {image_description}")

        # 3) Compare to goal
        config['image_description'] = image_description
        analyze_dict = analyze_image(image_path, config, stage="analyze")
        alignment_analysis = analyze_dict["response"]
        print(f"Alignment Analysis: {alignment_analysis}")

        # 4) Log iteration data
        iteration_log_path = os.path.join(run_directory, f"iteration_{iteration}.json")

        # 5) Refine prompt for next iteration
        if progress_callback:
            progress_callback({
                'stage': 'refinement',
                'message': f'Refining prompt for iteration {iteration + 1}...',
                'progress': 10 + (iteration * 90 / max_iters),
                'iteration': iteration,
                'max_iterations': max_iters
            })

        refined_dict = refine_prompt(
            current_prompt,
            goal,
            image_description,
            alignment_analysis,
            config
        )
        raw_refined_response = refined_dict["response"]
        refined_prompt = extract_prompt_tags(raw_refined_response)
        if not refined_prompt:
            refined_prompt = raw_refined_response.strip()

        # Store everything in iteration_{iteration}.json
        iteration_data = {
            "iteration": iteration,
            "goal": goal,
            "prompt": current_prompt,
            "image_path": image_path,
            "image_description": image_description,
            "alignment_analysis": alignment_analysis,
            "timestamp": datetime.now().isoformat(),
            "vision_interactions": [
                {
                    "stage": "describe",
                    "system_prompt": describe_dict["system_prompt"],
                    "user_prompt": describe_dict["user_prompt"],
                    "response": describe_dict["response"]
                },
                {
                    "stage": "analyze",
                    "system_prompt": analyze_dict["system_prompt"],
                    "user_prompt": analyze_dict["user_prompt"],
                    "response": analyze_dict["response"]
                }
            ],
            "text_interactions": [
                {
                    "stage": "refine_prompt",
                    "system_prompt": refined_dict["system_prompt"],
                    "user_prompt": refined_dict["user_prompt"],
                    "response": refined_dict["response"]
                }
            ],
            "next_prompt": refined_prompt
        }

        with open(iteration_log_path, "w", encoding="utf-8") as f:
            json.dump(iteration_data, f, indent=2)

        # 6) Check for success indicators (optional)
        success_indicators = [
            "perfectly matches",
            "all elements align",
            "complete match",
            "fully achieves the goal"
        ]
        if any(indicator in alignment_analysis.lower() for indicator in success_indicators):
            if progress_callback:
                progress_callback({
                    'stage': 'complete',
                    'message': 'Goal achieved successfully!',
                    'progress': 100,
                    'iteration': iteration,
                    'max_iterations': max_iters,
                    'status': 'success'
                })
            print("\nGoal achieved successfully!")
            break

        # Continue
        current_prompt = refined_prompt

    if progress_callback:
        progress_callback({
            'stage': 'complete',
            'message': 'All iterations completed',
            'progress': 100,
            'iteration': iteration,
            'max_iterations': max_iters,
            'status': 'complete'
        })

    print("\nAll iterations completed.")
