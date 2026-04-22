# Automated TMK Evaluation Framework

Tools for evaluating Task-Method-Knowledge (TMK) models against reference textbook material. The framework supports both **Syntactic Metrics** (rule-based structure and vocabulary checks) and **Semantic Metrics** (LLM-based reasoning quality checks).

This directory is part of the [TMK-Text-to-Model](https://github.com/DILab-Ivy/TMK-Text-to-Model) repository. Schema validation uses the schemata defined in `../tmk-syntax-validator/schemata/`.

## Quick Start (Single Lesson)

The repo ships with a **Frames** example — a Raw (LLM-generated) and Refined (human-verified) TMK pair plus the lesson PDF.

```bash
pip install -r requirements.txt
python3 run_evaluation.py
```

This compares `RAW_TMK/` vs `REFINED_TMK/` against `lectures/Frames.pdf` and outputs `evaluation_results.xlsx`.

### Evaluate Your Own Lesson

Replace the example data with your own:

1. Put your LLM-generated TMK in `RAW_TMK/` (Task.json, Method.json, Knowledge.json)
2. Put your human-refined TMK in `REFINED_TMK/`
3. Place your lesson PDF in `lectures/`

```bash
python3 run_evaluation.py --raw RAW_TMK/ --refined REFINED_TMK/ --pdf lectures/YourLesson.pdf
```

### Include Semantic Metrics

Semantic evaluation uses an LLM-as-a-judge (requires OpenAI API key, costs money):

```bash
export OPENAI_API_KEY="your-key-here"
python3 run_evaluation.py --semantic --model gpt-4o
```

## Full Batch Evaluation (All Lessons)

If you have access to the full MCM-TMK repository with all lesson TMKs:

```bash
export MCM_TMK_PATH="/path/to/MCM-TMK/mcm/TMKs/Ivy"
export KBAI_PDF_PATH="/path/to/lectures/kbai_ebook.pdf"
python3 run_full_evaluation.py
```

Filter to a specific lesson:
```bash
python3 run_full_evaluation.py --lesson "Planning" --semantic
```

## Features

*   **Syntactic Evaluation**:
    *   **Instructional Alignment**: Vocabulary overlap between `Knowledge.json` and the lesson PDF.
    *   **Structural Semantics**: JSON schema compliance (via `../tmk-syntax-validator/schemata/`) and graph connectivity (bindings).
    *   **Procedural Semantics**: FSM guard logic, failure modeling, and hierarchy depth.
*   **Semantic Evaluation** (requires OpenAI API Key):
    *   **Causal Reasoning Quality**: Depth of causal mechanisms in `Method.json`.
    *   **Teleological Reasoning Quality**: Clarity of goal decomposition.
    *   **Procedural Fidelity**: Adhesion to the textbook's algorithmic steps.

## Output

| Script | Output |
|---|---|
| `run_evaluation.py` | `evaluation_results.xlsx` — Raw vs Refined comparison for one lesson |
| `run_full_evaluation.py` | `full_evaluation_results.xlsx` — Per-lesson detail + summary across all lessons |

## Core Files
*   `run_evaluation.py`: Single-lesson Raw vs Refined comparison (start here).
*   `run_full_evaluation.py`: Batch evaluation across all lessons (requires MCM-TMK access).
*   `tmk_evaluator.py`: All Syntactic metrics.
*   `semantic_evaluator.py`: All Semantic metrics using `deepeval`.
