import os
import re
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter
import json
import sys

# Import evaluators (assuming they are in current dir or pythonpath)
import tmk_evaluator
import semantic_evaluator

# Paths — update these to match your local environment
MCM_PATH = os.environ.get("MCM_TMK_PATH", os.path.join(os.path.dirname(__file__), "..", "MCM-TMK", "mcm", "TMKs", "Ivy"))
RAW_PATH = os.environ.get("RAW_TMK_PATH", MCM_PATH)
PDF_PATH = os.environ.get("KBAI_PDF_PATH", os.path.join(os.path.dirname(__file__), "lectures", "kbai_ebook.pdf"))
OUTPUT_EXCEL = "full_evaluation_results.xlsx"
TEMP_PDF_DIR = "temp_lesson_pdfs"

if not os.path.exists(TEMP_PDF_DIR):
    os.makedirs(TEMP_PDF_DIR)

# Lesson Mapping (Name -> Page Range)
# Based on TOC output
LESSON_PAGES = {
    "Semantic Networks": (27, 42),
    "Generate & Test": (42, 52),
    "Means-Ends Analysis": (52, 66),
    "Production Systems": (66, 81),
    "Frames": (81, 92),
    "Learning by Recording Cases": (92, 100),
    "Case-Based Reasoning": (100, 118),
    "Incremental Concept Learning": (118, 135),
    "Classification": (135, 148),
    "Logic": (148, 171),
    "Planning": (171, 188),
    "Understanding": (188, 199),
    "Commonsense Reasoning": (199, 211),
    "Scripts": (211, 222),
    "Explanation-Based Learning": (222, 232),
    "Analogical Reasoning": (232, 250),
    "Version Spaces": (250, 267),
    "Constraint Propagation": (267, 279),
    "Configuration": (279, 291),
    "Diagnosis": (291, 303),
    "Learning by Correcting Mistakes": (303, 314),
    "Meta-Reasoning": (314, 326),
    "Advanced Topics": (326, 342)
}

# Folder to Lesson Name Map
FOLDER_MAP = {
    "SemanticNetworks": "Semantic Networks",
    "GenerateAndTest": "Generate & Test",
    "MeansEndAnalysis": "Means-Ends Analysis",
    "ProductionSystems": "Production Systems",
    "Frames": "Frames",
    "LearningByRecordingCases": "Learning by Recording Cases",
    "CaseBasedReasoning": "Case-Based Reasoning",
    "IncrementalConceptLearning": "Incremental Concept Learning",
    "Classification": "Classification",
    "Logic": "Logic",
    "Planning": "Planning",
    "Understanding": "Understanding",
    "CommonsenseReasoning": "Commonsense Reasoning",
    "Scripts": "Scripts",
    "ExplanationBasedLearning": "Explanation-Based Learning",
    "AnalogicalReasoning": "Analogical Reasoning",
    "VersionSpaces": "Version Spaces",
    "ConstraintPropagation": "Constraint Propagation",
    "Configuration": "Configuration",
    "Diagnosis": "Diagnosis",
    "LearningByCorrectingMistakes": "Learning by Correcting Mistakes",
    "MetaReasoning": "Meta-Reasoning",
    "AdvancedTopics": "Advanced Topics"
}

def split_pdf(start_page, end_page, output_path):
    """Splits the main PDF to extract lesson pages."""
    try:
        reader = PdfReader(PDF_PATH)
        writer = PdfWriter()
        
        for i in range(start_page, end_page):
            if i < len(reader.pages):
                writer.add_page(reader.pages[i])
        
        with open(output_path, "wb") as f:
            writer.write(f)
        return True
    except Exception as e:
        print(f"Error splitting PDF: {e}")
        return False

def get_pair_from_base(base, refined_candidates, raw_map):
    pair = None
    lower_base = base.lower()
    
    if lower_base in raw_map:
        raw_name = raw_map[lower_base]
        
        lesson_name = FOLDER_MAP.get(base)
        if not lesson_name:
             # Try direct match
             if base in FOLDER_MAP:
                 lesson_name = FOLDER_MAP[base]
             else:
                 # Fuzzy match key
                 for k, v in FOLDER_MAP.items():
                     if k.lower() == lower_base:
                         lesson_name = v
                         break

        if lesson_name:
             # Find actual refined dir name
             # We passed 'base', we need full name.
             # Iterate candidates
             ref_name = None
             for r in refined_candidates:
                 if r.startswith(base) and (r.endswith("_v0") or r.endswith("_V0")):
                     ref_name = r
                     break
             if ref_name:
                pair = {
                    "Lesson": lesson_name,
                    "Refined_Dir": os.path.join(MCM_PATH, ref_name),
                    "Raw_Dir": os.path.join(RAW_PATH, raw_name),
                    "Refined_Name": ref_name,
                    "Raw_Name": raw_name
                }
    return pair

def get_tmk_pairs():
    refined_candidates = [d for d in os.listdir(MCM_PATH) if os.path.isdir(os.path.join(MCM_PATH, d)) and (d.endswith("_v0") or d.endswith("_V0"))]
    raw_candidates = [d for d in os.listdir(RAW_PATH) if os.path.isdir(os.path.join(RAW_PATH, d))]
    
    pairs = []
    raw_map = {name.lower(): name for name in raw_candidates}
    
    # Iterate through refined candidates
    for ref in refined_candidates:
        base = re.sub(r'_[vV]0$', '', ref)
        
        # Mapping Logic
        if base == "CBR": base = "CaseBasedReasoning"
        if base == "RecordingCases": base = "LearningByRecordingCases"
        if base == "GPP": base = "GenerateAndTest"
        if base == "SemanticNetworksLogic": base = "SemanticNetworks"

        # Explicit skip for duplicate GPP if we have GenerateAndTest_v0
        if ref == "GPP_v0" and any(c.startswith("GenerateAndTest_v0") for c in refined_candidates):
            continue
            
        lower_base = base.lower()
        
        if lower_base in raw_map:
            raw_name = raw_map[lower_base]
            
            # Resolve Lesson Name
            lesson_name = None
            if base in FOLDER_MAP:
                lesson_name = FOLDER_MAP[base]
            else:
                 # Check manually
                 for k, v in FOLDER_MAP.items():
                     if k.lower() == lower_base:
                         lesson_name = v
                         break
            
            if lesson_name:
                pairs.append({
                    "Lesson": lesson_name,
                    "Refined_Dir": os.path.join(MCM_PATH, ref),
                    "Raw_Dir": os.path.join(RAW_PATH, raw_name),
                    "Refined_Name": ref,
                    "Raw_Name": raw_name
                })
            else:
                print(f"Warning: No Lesson Map for {base} (Refined: {ref})")

    return pairs

def run_evaluations(target_lesson=None, enable_semantic=False, model="gpt-4o"):
    pairs = get_tmk_pairs()
    all_results = []
    
    print(f"Found {len(pairs)} pairs to evaluate.")
    
    if target_lesson:
        pairs = [p for p in pairs if p['Lesson'] == target_lesson]
        print(f"Filtered to {len(pairs)} pairs for lesson: {target_lesson}")

    for pair in pairs:
        lesson = pair['Lesson']
        print(f"\nProcessing {lesson}...")
        
        if lesson not in LESSON_PAGES:
            print(f"Skipping: No page range for {lesson}")
            continue
            
        # 1. Split PDF
        start, end = LESSON_PAGES[lesson]
        lesson_pdf_path = os.path.join(TEMP_PDF_DIR, f"{lesson.replace(' ', '_')}.pdf")
        if not split_pdf(start, end, lesson_pdf_path):
            continue
            
        # 2. Evaluate Refined
        print(f"  Evaluating Refined: {pair['Refined_Name']}")
        try:
            ref_syn = tmk_evaluator.evaluate_tmk(pair['Refined_Dir'], lesson_pdf_path)
        except Exception as e:
            print(f"    Error in Syntactic Eval: {e}")
            ref_syn = {}
            
        ref_sem = {}
        if enable_semantic:
            try:
                 # Use skip_knowledge=True to save context
                ref_sem = semantic_evaluator.evaluate_semantics(pair['Refined_Dir'], lesson_pdf_path, model_name=model, skip_knowledge=True)
            except Exception as e:
                print(f"    Error in Semantic Eval: {e}")
                ref_sem = {}

        # 3. Evaluate Raw
        print(f"  Evaluating Raw: {pair['Raw_Name']}")
        try:
            raw_syn = tmk_evaluator.evaluate_tmk(pair['Raw_Dir'], lesson_pdf_path)
        except Exception as e:
            print(f"    Error in Syntactic Eval: {e}")
            raw_syn = {}
            
        raw_sem = {}
        if enable_semantic:
            try:
                raw_sem = semantic_evaluator.evaluate_semantics(pair['Raw_Dir'], lesson_pdf_path, model_name=model, skip_knowledge=True)
            except Exception as e:
                print(f"    Error in Semantic Eval: {e}")
                raw_sem = {}

        # 4. Compile Row
        def get_score(source, key1, key2):
            return source.get(key1, {}).get(key2, 0.0)
            
        def get_sem_score(source, metric):
            return source.get(metric, {}).get("score", 0.0)
            
        def get_sem_reason(source, metric):
            return source.get(metric, {}).get("reason", "")

        row = {
            "Lesson": lesson,
            
            # --- Refined ---
            "Ref_Instructional": ref_syn.get("instructional_alignment", 0.0),
            
            # Refined Scores
            "Ref_Struct_Task": ref_syn.get("structural_validation", {}).get("Task", 0.0),
            "Ref_Struct_Method": ref_syn.get("structural_validation", {}).get("Method", 0.0),
            "Ref_Struct_Know": ref_syn.get("structural_validation", {}).get("Knowledge", 0.0),
            "Ref_Bind_TM": ref_syn.get("bindings", {}).get("task_method_binding", 0.0),
            "Ref_Bind_MK": ref_syn.get("bindings", {}).get("method_knowledge_binding", 0.0),
            "Ref_Bind_TK": ref_syn.get("bindings", {}).get("task_knowledge_binding", 0.0),
            "Ref_Proc_Guards": ref_syn.get("procedural_semantics", {}).get("guard_logic", 0.0),
            "Ref_Proc_Fail": ref_syn.get("procedural_semantics", {}).get("failure_modeling", 0.0),
            "Ref_Proc_Teleo": ref_syn.get("procedural_semantics", {}).get("teleology", 0.0),
            "Ref_Proc_Approp": ref_syn.get("procedural_semantics", {}).get("appropriateness", 0.0),
            "Ref_Proc_Depth": ref_syn.get("procedural_semantics", {}).get("hierarchy_depth", 0.0),
            
            "Ref_Sem_Causal": get_sem_score(ref_sem, "Causal Mechanistic Depth"),
            "Ref_Sem_Teleo": get_sem_score(ref_sem, "Goal Operationalization Specificity"),
            "Ref_Sem_Fidelity": get_sem_score(ref_sem, "Algorithmic Nuance & Fidelity"),

            # --- Raw ---
            "Raw_Instructional": raw_syn.get("instructional_alignment", 0.0),
            "Raw_Struct_Task": raw_syn.get("structural_validation", {}).get("Task", 0.0),
            "Raw_Struct_Method": raw_syn.get("structural_validation", {}).get("Method", 0.0),
            "Raw_Struct_Know": raw_syn.get("structural_validation", {}).get("Knowledge", 0.0),
            "Raw_Bind_TM": raw_syn.get("bindings", {}).get("task_method_binding", 0.0),
            "Raw_Bind_MK": raw_syn.get("bindings", {}).get("method_knowledge_binding", 0.0),
            "Raw_Bind_TK": raw_syn.get("bindings", {}).get("task_knowledge_binding", 0.0),
            "Raw_Proc_Guards": raw_syn.get("procedural_semantics", {}).get("guard_logic", 0.0),
            "Raw_Proc_Fail": raw_syn.get("procedural_semantics", {}).get("failure_modeling", 0.0),
            "Raw_Proc_Teleo": raw_syn.get("procedural_semantics", {}).get("teleology", 0.0),
            "Raw_Proc_Approp": raw_syn.get("procedural_semantics", {}).get("appropriateness", 0.0),
            "Raw_Proc_Depth": raw_syn.get("procedural_semantics", {}).get("hierarchy_depth", 0.0),
            
            "Raw_Sem_Causal": get_sem_score(raw_sem, "Causal Mechanistic Depth"),
            "Raw_Sem_Teleo": get_sem_score(raw_sem, "Goal Operationalization Specificity"),
            "Raw_Sem_Fidelity": get_sem_score(raw_sem, "Algorithmic Nuance & Fidelity"),

            "Ref_Sem_Causal_Reason": get_sem_reason(ref_sem, "Causal Mechanistic Depth"),
            "Ref_Sem_Teleo_Reason": get_sem_reason(ref_sem, "Goal Operationalization Specificity"),
            "Ref_Sem_Fidelity_Reason": get_sem_reason(ref_sem, "Algorithmic Nuance & Fidelity"),
        }
        all_results.append(row)

    df_detailed = pd.DataFrame(all_results)
    
    # 5. Calculate Averages for Summary
    metrics_map = [
        ("Instructional Alignment", "Instructional"),
        ("Struct: Task", "Struct_Task"),
        ("Struct: Method", "Struct_Method"),
        ("Struct: Knowledge", "Struct_Know"),
        ("Binding: Task-Method", "Bind_TM"),
        ("Binding: Method-Knowledge", "Bind_MK"),
        ("Binding: Task-Knowledge", "Bind_TK"),
        ("Proc: Guard Logic", "Proc_Guards"),
        ("Proc: Failure Modeling", "Proc_Fail"),
        ("Proc: Teleology", "Proc_Teleo"),
        ("Proc: Appropriateness", "Proc_Approp"),
        ("Proc: Hierarchy Depth", "Proc_Depth"),
        ("Sem: Causal", "Sem_Causal"),
        ("Sem: Teleology", "Sem_Teleo"),
        ("Sem: Fidelity", "Sem_Fidelity"),
    ]
    
    summary_rows = []
    for label, suffix in metrics_map:
        raw_key = f"Raw_{suffix}"
        ref_key = f"Ref_{suffix}"
        
        # Calculate mean, ignoring zeros if that's desired? Or strict mean?
        # User said "average score across all TMKs". Strict mean includes 0s.
        raw_avg = df_detailed[raw_key].mean() if raw_key in df_detailed.columns else 0.0
        ref_avg = df_detailed[ref_key].mean() if ref_key in df_detailed.columns else 0.0
        
        summary_rows.append({
            "Metric": label,
            "Raw Average": raw_avg,
            "Refined Average": ref_avg,
            "Diff (Ref - Raw)": ref_avg - raw_avg
        })
        
    df_summary = pd.DataFrame(summary_rows)

    # 6. Save to Excel with multiple sheets
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        df_detailed.to_excel(writer, sheet_name="Detailed Results", index=False)
        df_summary.to_excel(writer, sheet_name="Summary Comparison", index=False)
        
    print(f"\nEvaluation Complete. Results saved to {OUTPUT_EXCEL} (2 sheets)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Full TMK Evaluation")
    parser.add_argument("--lesson", type=str, help="Run only for a specific lesson (e.g., 'Commonsense Reasoning')")
    parser.add_argument("--semantic", action="store_true", help="Enable Semantic Evaluation (requires API key)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="LLM Model for semantic eval")
    
    args = parser.parse_args()
    
    run_evaluations(args.lesson, args.semantic, args.model)
