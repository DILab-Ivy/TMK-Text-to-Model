"""
Standalone TMK Evaluation: Compare a Raw vs Refined TMK pair for a single lesson.

Default example uses the included Frames lesson data:
    RAW_TMK/        — LLM-generated TMK
    REFINED_TMK/    — Human-refined TMK
    lectures/Frames.pdf — Reference lesson PDF

To evaluate your own lesson, replace those folders and PDF, then run:
    python3 run_evaluation.py --raw YOUR_RAW/ --refined YOUR_REFINED/ --pdf YOUR_LESSON.pdf
"""

import os
import sys
import argparse
import pandas as pd

# Ensure this script's directory is on the path so imports work
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import tmk_evaluator
import semantic_evaluator


def evaluate_pair(raw_dir, refined_dir, reference_pdf, enable_semantic=False, model="gpt-4o"):
    """Evaluate a single Raw vs Refined TMK pair."""

    results = {}

    for label, tmk_dir in [("Refined", refined_dir), ("Raw", raw_dir)]:
        print(f"\n{'='*60}")
        print(f"Evaluating {label}: {tmk_dir}")
        print(f"{'='*60}")

        # Syntactic
        try:
            syn = tmk_evaluator.evaluate_tmk(tmk_dir, reference_pdf)
        except Exception as e:
            print(f"  Error in Syntactic Eval: {e}")
            syn = {}

        # Semantic (optional)
        sem = {}
        if enable_semantic:
            try:
                sem = semantic_evaluator.evaluate_semantics(
                    tmk_dir, reference_pdf, model_name=model, skip_knowledge=True
                )
            except Exception as e:
                print(f"  Error in Semantic Eval: {e}")

        results[label] = {"syn": syn, "sem": sem}

    return results


def build_report(results, output_path):
    """Build a comparison report and save to Excel."""

    def get(src, *keys, default=0.0):
        val = src
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val

    def sem_score(src, metric):
        return src.get(metric, {}).get("score", 0.0)

    metrics = [
        ("Instructional Alignment",   lambda s: get(s["syn"], "instructional_alignment")),
        ("Struct: Task",              lambda s: get(s["syn"], "structural_validation", "Task")),
        ("Struct: Method",            lambda s: get(s["syn"], "structural_validation", "Method")),
        ("Struct: Knowledge",         lambda s: get(s["syn"], "structural_validation", "Knowledge")),
        ("Binding: Task-Method",      lambda s: get(s["syn"], "bindings", "task_method_binding")),
        ("Binding: Method-Knowledge", lambda s: get(s["syn"], "bindings", "method_knowledge_binding")),
        ("Binding: Task-Knowledge",   lambda s: get(s["syn"], "bindings", "task_knowledge_binding")),
        ("Proc: Guard Logic",         lambda s: get(s["syn"], "procedural_semantics", "guard_logic")),
        ("Proc: Failure Modeling",    lambda s: get(s["syn"], "procedural_semantics", "failure_modeling")),
        ("Proc: Teleology",           lambda s: get(s["syn"], "procedural_semantics", "teleology")),
        ("Proc: Appropriateness",     lambda s: get(s["syn"], "procedural_semantics", "appropriateness")),
        ("Proc: Hierarchy Depth",     lambda s: get(s["syn"], "procedural_semantics", "hierarchy_depth")),
        ("Sem: Causal",               lambda s: sem_score(s["sem"], "Causal Reasoning Quality")),
        ("Sem: Teleology",            lambda s: sem_score(s["sem"], "Teleological Reasoning Quality")),
        ("Sem: Fidelity",             lambda s: sem_score(s["sem"], "Procedural Fidelity")),
    ]

    rows = []
    for label, fn in metrics:
        raw_val = fn(results["Raw"])
        ref_val = fn(results["Refined"])
        rows.append({
            "Metric": label,
            "Raw": raw_val,
            "Refined": ref_val,
            "Diff (Refined - Raw)": ref_val - raw_val,
        })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Comparison", index=False)

    print(f"\nResults saved to {output_path}")
    print("\n" + df.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate a Raw vs Refined TMK pair against a reference PDF."
    )
    parser.add_argument("--raw", type=str,
                        default=os.path.join(SCRIPT_DIR, "RAW_TMK"),
                        help="Path to Raw TMK directory (default: RAW_TMK/)")
    parser.add_argument("--refined", type=str,
                        default=os.path.join(SCRIPT_DIR, "REFINED_TMK"),
                        help="Path to Refined TMK directory (default: REFINED_TMK/)")
    parser.add_argument("--pdf", type=str,
                        default=os.path.join(SCRIPT_DIR, "lectures", "Frames.pdf"),
                        help="Path to reference lesson PDF (default: lectures/Frames.pdf)")
    parser.add_argument("--output", type=str, default="evaluation_results.xlsx",
                        help="Output Excel file (default: evaluation_results.xlsx)")
    parser.add_argument("--semantic", action="store_true",
                        help="Enable Semantic Evaluation (requires OPENAI_API_KEY)")
    parser.add_argument("--model", type=str, default="gpt-4o",
                        help="LLM model for semantic eval (default: gpt-4o)")

    args = parser.parse_args()

    results = evaluate_pair(args.raw, args.refined, args.pdf, args.semantic, args.model)
    build_report(results, args.output)
