import os
import json
from datetime import datetime
import difflib

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

    # First iteration: Baseline analysis
    if iteration == 1:
        return True, "Initial iteration establishing baseline image and prompt effectiveness"

    # Second iteration: Comparative analysis
    if iteration == 2:
        prompt_changes = analyze_prompt_differences(previous_prompt, current_prompt)
        image_impact = compare_analyses(previous_analyses[-1], analysis)
        return True, f"Analyzing prompt-to-image relationship: {prompt_changes} resulted in {image_impact}"

    # Third iteration: Learning and synthesis
    if iteration == 3:
        synthesis = synthesize_learning(previous_analyses, analysis, previous_prompt, current_prompt)
        return True, f"Synthesizing learnings from previous iterations: {synthesis}"

    # After third iteration: Comprehensive evaluation
    success_phrases = [
        "perfectly matches",
        "excellent match",
        "captures all elements",
        "achieves the goal",
        "outstanding representation"
    ]
    if any(phrase in analysis.lower() for phrase in success_phrases):
        return False, "Analysis indicates perfect match based on comprehensive evaluation"

    # Check for substantial improvements needed
    improvement_phrases = [
        "could be improved",
        "needs adjustment",
        "would benefit from",
        "consider adding",
        "should include"
    ]
    if not any(phrase in analysis.lower() for phrase in improvement_phrases):
        return False, "No substantial improvements needed after thorough analysis"

    return True, "Continuing iterations based on identified areas for enhancement"

def analyze_prompt_differences(prev_prompt, curr_prompt):
    """Analyze how the prompt changed and what we're testing."""
    if not prev_prompt:
        return "Initial prompt exploration"
    
    # Split prompts into words for comparison
    prev_words = set(prev_prompt.lower().split())
    curr_words = set(curr_prompt.lower().split())
    
    added = curr_words - prev_words
    removed = prev_words - curr_words
    
    changes = []
    if added:
        changes.append(f"Added emphasis on: {', '.join(added)}")
    if removed:
        changes.append(f"Reduced emphasis on: {', '.join(removed)}")
    
    return "; ".join(changes) if changes else "Refined existing elements"

def compare_analyses(prev_analysis, curr_analysis):
    """Compare how the image changed based on the analyses."""
    if not prev_analysis:
        return "Initial image assessment"
    
    # Look for key phrases indicating changes
    improvements = []
    regressions = []
    
    # Common improvement indicators
    better_phrases = ["better", "improved", "enhanced", "stronger", "clearer"]
    worse_phrases = ["less", "weaker", "reduced", "lost", "missing"]
    
    for phrase in better_phrases:
        if phrase in curr_analysis.lower():
            improvements.append(phrase)
    
    for phrase in worse_phrases:
        if phrase in curr_analysis.lower():
            regressions.append(phrase)
    
    if improvements and not regressions:
        return f"Improvements noted in: {', '.join(improvements)}"
    elif regressions and not improvements:
        return f"Regressions noted in: {', '.join(regressions)}"
    elif improvements and regressions:
        return f"Mixed results: improved {', '.join(improvements)} but regressed in {', '.join(regressions)}"
    else:
        return "Subtle changes with no clear improvement or regression"

def synthesize_learning(prev_analyses, curr_analysis, prev_prompt, curr_prompt):
    """Synthesize what we've learned from the first three iterations."""
    if len(prev_analyses) < 2:
        return "Insufficient data for synthesis"
    
    # Analyze prompt evolution
    prompt_evolution = analyze_prompt_differences(prev_prompt, curr_prompt)
    
    # Look for patterns in the analyses
    consistent_issues = []
    improvements = []
    
    # Common phrases to track
    issue_phrases = ["missing", "lacks", "needs", "could use", "should have"]
    improvement_phrases = ["better", "improved", "enhanced", "stronger", "clearer"]
    
    # Track issues and improvements across all analyses
    for analysis in [*prev_analyses, curr_analysis]:
        for phrase in issue_phrases:
            if phrase in analysis.lower():
                consistent_issues.append(phrase)
        for phrase in improvement_phrases:
            if phrase in analysis.lower():
                improvements.append(phrase)
    
    # Count frequencies to identify patterns
    from collections import Counter
    consistent_issues = [issue for issue, count in Counter(consistent_issues).items() if count >= 2]
    recurring_improvements = [imp for imp, count in Counter(improvements).items() if count >= 2]
    
    synthesis = []
    if consistent_issues:
        synthesis.append(f"Persistent challenges: {', '.join(consistent_issues)}")
    if recurring_improvements:
        synthesis.append(f"Consistent improvements: {', '.join(recurring_improvements)}")
    if prompt_evolution:
        synthesis.append(f"Prompt evolution: {prompt_evolution}")
    
    return "; ".join(synthesis) if synthesis else "No clear patterns identified yet"

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
    previous_prompt = None
    previous_analyses = []
    iteration_history = []

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

        # 3) Evaluate quality and decide whether to continue
        should_continue, reason = evaluate_quality(
            analysis, 
            current_prompt, 
            previous_prompt, 
            config, 
            iteration,
            previous_analyses
        )
        
        # 4) Log iteration data
        log_data = {
            "iteration": iteration,
            "goal": goal,
            "prompt_before": current_prompt,
            "analysis": analysis,
            "image_path": image_path,
            "timestamp": datetime.now().isoformat(),
            "quality_check": {
                "should_continue": should_continue,
                "reason": reason
            }
        }

        # Save JSON log
        iteration_log_path = os.path.join(run_directory, f"iteration_{iteration}.json")
        with open(iteration_log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)

        if not should_continue:
            print(f"\nStopping iterations: {reason}")
            break

        # Store current analysis and iteration data for future comparison
        previous_analyses.append(analysis)
        iteration_history.append(log_data)

        # 5) Refine prompt for next iteration
        previous_prompt = current_prompt
        current_prompt = refine_prompt(
            current_prompt, 
            analysis, 
            config, 
            iteration=iteration,
            previous_iterations=iteration_history
        )
        print(f"Refined prompt: {current_prompt}")
        log_data["prompt_after"] = current_prompt

        # Update the log with the new prompt
        with open(iteration_log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)

    print("\nAll iterations completed.") 