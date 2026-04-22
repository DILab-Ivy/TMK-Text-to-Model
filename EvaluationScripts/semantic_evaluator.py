import os
import json
import argparse
import pdfplumber
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval import evaluate
from typing import Dict, Any

# --- Helper Functions ---

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def load_tmk_content(tmk_dir: str, skip_knowledge: bool = False) -> str:
    """Loads and serializes Task, Method, and (optionally) Knowledge JSONs."""
    content = ""
    files = ['Task.json', 'Method.json']
    if not skip_knowledge:
        files.append('Knowledge.json')
        
    for filename in files:
        path = os.path.join(tmk_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    content += f"\n--- {filename} ---\n"
                    content += json.dumps(data, indent=2)
            except Exception as e:
                print(f"Error reading {path}: {e}")
    return content

# --- Metric Definitions ---



def get_causal_metric(model_name="gpt-4o"):
    return GEval(
        name="Causal Reasoning Quality",
        criteria="""
        Evaluate the SEMANTIC DEPTH of the state transitions in the Actual Output (TMK JSONs) relative to the Context.

        Scoring:
        - 1-2: Output is oversimplified, uses "Black Box" labels, or tautological transitions. Ignores variables, conditions, or implicit causal links.
        - 3: Output captures basic cause-effect correctly but misses implicit causal links or details.
        - 4-5: Output exposes underlying mechanisms, references domain-specific variables, and captures implicit causal links described in the text.

        Notes:
        - Ignore structural differences (order of states, extra intermediate nodes) if the logic is correct.
        - Reward outputs that clarify the causal reasoning; penalize outputs that oversimplify or omit explicit criteria.
        - Provide a short explanation of why this score was assigned, referencing specific transitions or conditions.
        """,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        model=model_name  # <-- Ensures GPT-4o explains reasoning
    )

def get_teleological_metric(model_name="gpt-4o"):
    return GEval(
        name="Teleological Reasoning Quality",
        criteria="""
        Evaluate how concrete and specific the goal decomposition is relative to the Context.

        Scoring:
        - 1-2: Goal hierarchy is shallow; subgoals are vague or just rephrased parent goals; intermediate conceptual steps are missing.
        - 3: Goal hierarchy captures basic decomposition but omits some intermediate or methodological details.
        - 4-5: High-level goals are broken into concrete, executable sub-operations; goalInvocation links high-level intent to methods; subgoals are semantically precise and capture all intermediate steps described in the text.

        Notes:
        - Ignore ordering of goals and minor formatting differences.
        - Reward additional details only if they are supported by the text.
        - Provide a short explanation citing specific subgoals, methods, or goalInvocation links that justify the score.
        """,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        model=model_name
    )

def get_procedural_fidelity_metric(model_name="gpt-4o"):
    return GEval(
        name="Procedural Fidelity",
        criteria="""
        Evaluate the fidelity and richness of the procedural steps in Method.json relative to the Context.

        Scoring:
        - 1-2: Procedure captures only a "happy path"; ignores loops, error handling, or complex data manipulations.
        - 3: Procedure captures basic steps but misses some domain-specific nuances or iterative refinement described in the text.
        - 4-5: Procedure is detailed and semantically rich, including edge cases, failure modes, iterative refinement, and semantically precise operations as described in the text.

        Notes:
        - Reward extra steps only if they reflect content from the text; ignore irrelevant additions.
        - Ignore minor structural differences (order of states, extra intermediate nodes) if the semantic logic is correct.
        - Provide a short explanation citing specific states, loops, or failure handling that justify the score.
        """,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        model=model_name
    )



# --- Main Evaluation Logic ---

def evaluate_semantics(tmk_dir: str, reference_pdf: str, model_name="gpt-4o", skip_knowledge: bool = False):
    print(f"\n--- Semantic Evaluation for: {tmk_dir} ---")
    
    # 1. Prepare Data
    reference_text = extract_text_from_pdf(reference_pdf)
    
    # Truncate text context to avoid token limits
    if len(reference_text) > 40000:
        print("Warning: Reference text is very long, truncating to 40k chars for API cost/limit safety.")
        reference_text = reference_text[:40000]
        
    tmk_content = load_tmk_content(tmk_dir, skip_knowledge)
    
    # 2. Create Test Case
    test_case = LLMTestCase(
        input="Construct a detailed Task-Method-Knowledge (TMK) model representing the cognitive process described in the context.",
        actual_output=tmk_content,
        context=[reference_text]
    )
    
    # 3. Define Metrics
    metrics = [
        get_causal_metric(model_name),
        get_teleological_metric(model_name),
        get_procedural_fidelity_metric(model_name)
    ]
    
    # 4. Run Evaluation
    results = {}
    
    for metric in metrics:
        print(f"Running metric: {metric.name}...")
        try:
            metric.measure(test_case)
            print(f"  Score: {metric.score}")
            print(f"  Reason: {metric.reason}")
            results[metric.name] = {
                "score": metric.score,
                "reason": metric.reason
            }
        except Exception as e:
            print(f"  Error running metric {metric.name}: {e}")
            results[metric.name] = {"score": 0, "reason": str(e)}
            
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TMK Semantic Evaluator using DeepEval")
    parser.add_argument("--tmk_dir", type=str, required=True, help="Path to TMK directory")
    parser.add_argument("--pdf", type=str, required=True, help="Path to reference PDF")
    parser.add_argument("--model", type=str, default="gpt-4o", help="LLM Model to use (default: gpt-4o)")
    parser.add_argument("--skip_knowledge", action="store_true", help="Exclude Knowledge.json to reduce context size")
    
    args = parser.parse_args()
    
    evaluate_semantics(args.tmk_dir, args.pdf, args.model, args.skip_knowledge)
