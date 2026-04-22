# Automated TMK Evaluation Framework

Tools for evaluating Task-Method-Knowledge (TMK) models against reference textbook material. The framework supports both **Syntactic Metrics** (rule-based structure and vocabulary checks) and **Semantic Metrics** (LLM-based reasoning quality checks).

This directory is part of the [TMK-Text-to-Model](https://github.com/DILab-Ivy/TMK-Text-to-Model) repository. Schema validation uses the schemata defined in `../tmk-syntax-validator/schemata/`.

## Features

*   **Syntactic Evaluation**:
    *   **Instructional Alignment**: Checks vocabulary overlap between `Knowledge.json` and the lesson PDF.
    *   **Structural Semantics**: Validates JSON schema compliance (via `../tmk-syntax-validator/schemata/`) and graph connectivity (bindings).
    *   **Procedural Semantics**: Analyzes FSM guard logic, failure modeling, and hierarchy depth.
*   **Semantic Evaluation** (requires OpenAI API Key):
    *   **Causal Reasoning Quality**: Evaluates the depth of causal mechanisms in `Method.json`.
    *   **Teleological Reasoning Quality**: Evaluates the clarity of goal decomposition.
    *   **Procedural Fidelity**: Evaluates adhesion to the textbook's algorithmic steps.
*   **Comparative Analysis**: Automatically runs on "Raw" (LLM-generated) vs "Refined" (Human-verified) TMK pairs and generates a report.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Configure paths (pick one approach):

    **Option A** — Environment variables:
    ```bash
    export MCM_TMK_PATH="/path/to/MCM-TMK/mcm/TMKs/Ivy"
    export KBAI_PDF_PATH="/path/to/lectures/kbai_ebook.pdf"
    ```

    **Option B** — Default relative paths:
    If your directory layout looks like this, no configuration is needed:
    ```
    repo-root/
    ├── MCM-TMK/mcm/TMKs/Ivy/       # Refined + Raw TMKs
    ├── EvaluationScripts/           # This directory
    │   ├── lectures/kbai_ebook.pdf  # Reference PDF (not tracked in git)
    │   ├── run_full_evaluation.py
    │   └── ...
    └── tmk-syntax-validator/schemata/
    ```

3.  Set OpenAI API Key (only needed for semantic evaluation):
    ```bash
    export OPENAI_API_KEY="your-key-here"
    ```

## Usage

### Run Full Evaluation
To evaluate all TMK pairs (Syntactic only):
```bash
python3 run_full_evaluation.py
```

### Run with Semantic Metrics
To include LLM-as-a-judge metrics (costs money):
```bash
python3 run_full_evaluation.py --semantic --model gpt-4o
```

### Evaluate Specific Lesson
To run for a single lesson (e.g., "Planning"):
```bash
python3 run_full_evaluation.py --lesson "Planning" --semantic
```

## Output
The script generates `full_evaluation_results.xlsx` containing:
*   **Detailed Results**: Per-lesson scores for every metric.
*   **Summary Comparison**: Average scores for Raw vs Refined TMKs.

## Core Files
*   `run_full_evaluation.py`: Main entry point. Discovers TMK pairs and orchestrates evaluation.
*   `tmk_evaluator.py`: Implements all Syntactic metrics.
*   `semantic_evaluator.py`: Implements all Semantic metrics using `deepeval`.
