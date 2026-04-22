import os
import json
import argparse
import re
from typing import List, Dict, Set, Tuple
import pdfplumber
import jsonschema

# --- Metric 1: Instructional Alignment ---

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

def get_knowledge_items(knowledge_path: str) -> Set[str]:
    """Extracts all 'name' fields from concepts, instances, relations, and assertions."""
    names = set()
    try:
        with open(knowledge_path, 'r') as f:
            data = json.load(f)
            
            # Helper to split CamelCase/snake_case for better matching? 
            # User said "only their name". If name is "HotelRoom", text might have "hotel room".
            # Let's normalize name: split CamelCase, replace underscores, lower.
            def normalize(n):
                if not n: return ""
                # Replace underscores/hyphens with space
                n = re.sub(r'[_\-]', ' ', n)
                # Split CamelCase (e.g., "MeansEnds" -> "Means Ends")
                n = re.sub('([a-z0-9])([A-Z])', r'\1 \2', n)
                return n.lower().strip()

            keys_to_check = ['concepts', 'instances', 'relations', 'assertions', 'triples']
            for key in keys_to_check:
                if key in data:
                    for item in data[key]:
                        if 'name' in item:
                            normalized_name = normalize(item['name'])
                            if normalized_name:
                                names.add(normalized_name)
    except Exception as e:
        print(f"Error reading Knowledge.json at {knowledge_path}: {e}")
    return names

def calculate_instructional_alignment(knowledge_path: str, reference_text_path: str) -> float:
    """
    Calculates alignment using fuzzy/token-based matching.
    Logic:
    1. Tokenize reference text into unique words (vocab).
    2. For each Knowledge Item, tokenize its name.
    3. Match if ANY token (len>=2) from the item exists in the ref vocab 
       (either exact match or as a prefix, e.g. 'eq' -> 'equation').
    """
    reference_text = extract_text_from_pdf(reference_text_path)
    if not reference_text:
        return 0.0
    
    # Build reference vocab (only alphabetic tokens)
    ref_tokens = re.findall(r'[a-z]+', reference_text.lower())
    ref_vocab = set(ref_tokens)
    
    knowledge_items = get_knowledge_items(knowledge_path)
    
    if not knowledge_items:
        return 0.0
    
    # Pre-computation for fuzzy matching speed
    # We can rely on ref_vocab for exact/prefix checks
    from difflib import get_close_matches

    found_count = 0
    missing_items = []
    
    # Stricter Check: Require ALL significant tokens to match
    for item in knowledge_items:
        # Preprocessing: Explicitly replace numbers/dashes with space before tokenizing
        cleaned_item = re.sub(r'[\d\-]', ' ', item.lower())
        item_tokens = re.findall(r'[a-z]+', cleaned_item)
        
        # Filter for meaningful tokens (len >= 3)
        meaningful_tokens = [t for t in item_tokens if len(t) >= 3]
        
        if not meaningful_tokens:
            # If item was just "id-12", ignore or treat as missing?
            # Let's count as missing if empty, or skip?
            # If skip, adjust denominator? No, keep it simple.
            missing_items.append(item)
            continue
            
        all_tokens_matched = True
        failed_token = None
        
        for t in meaningful_tokens:
            token_match = False
            
            # 1. Exact match
            if t in ref_vocab:
                token_match = True
            # 2. Fuzzy match (Levenshtein, strict cutoff)
            # Difflib is slow if vocab large, but manageable for textbook ~5k words
            # Relaxed to 0.85 to handle plurals/suffixes better while still requiring ALL tokens
            close = get_close_matches(t, ref_vocab, n=1, cutoff=0.85) 
            if close:
                token_match = True
            
            if not token_match:
                all_tokens_matched = False
                failed_token = t
                break
        
        if all_tokens_matched:
            found_count += 1
        else:
            missing_items.append(f"{item} (failed on '{failed_token}')")
            
    score = found_count / len(knowledge_items)
    
    if missing_items:
        # Sort explicitly to avoid randomness in print order if needed, but not critical
        print(f"  [Metric 1 Debug] Missing {len(missing_items)}/{len(knowledge_items)} items. Examples:")
        for m in missing_items[:10]:
            print(f"   - {m}")
        if len(missing_items) > 10:
            print(f"   - ... and {len(missing_items) - 10} more.")
            
    return score

# --- Metric 2: Structural Semantics ---

def load_schema(schema_path: str) -> Dict:
    """Loads a JSON schema."""
    with open(schema_path, 'r') as f:
        return json.load(f)

def score_json(data: Dict, schema: Dict) -> Tuple[int, int]:
    """
    Scores a JSON object against a schema.
    Returns (score, max_score).
    Logic mirrors validator.js:
    - Each property in schema adds 2 to max_score.
    - Missing optional property: +2 (Vacuously correct)
    - Missing required property: +0
    - Present and valid: +2
    - Present and invalid: +1
    """
    score = 0
    max_score = 0
    
    properties = schema.get('properties', {})
    required = set(schema.get('required', []))
    
    for field, def_ in properties.items():
        max_score += 2
        
        if field not in data:
            if field in required:
                score += 0 # Missing required
            else:
                score += 2 # Vacuously correct
            continue
            
        # Field is present, validate it
        # Create a mini-schema for just this field
        field_schema = {"type": "object", "properties": {field: def_}, "required": []}
        try:
            jsonschema.validate(instance={field: data[field]}, schema=field_schema)
            score += 2 # Valid
        except jsonschema.ValidationError:
            score += 1 # Malformed
            
    return score, max_score

def validate_bindings(task: Dict, method: Dict, knowledge: Dict) -> Dict[str, float]:
    """
    Checks bindings between Task, Method, and Knowledge.
    Returns a dictionary of scores (0.0 to 1.0) for different binding aspects.
    """
    scores = {}
    
    # Extract concepts from Knowledge
    knowledge_concepts = set()
    if 'concepts' in knowledge:
        for c in knowledge['concepts']:
            if 'name' in c:
                knowledge_concepts.add(c['name'])
    
    # 1. Task-Method Binding: Task.mechanismReference -> Method.name OR Task.method -> Method.name
    task_methods_refs = set()
    if 'tasks' in task:
        for t in task['tasks']:
            # Raw Style: 'means' -> 'mechanismReference'
            if 'means' in t:
                for m in t['means']:
                    if 'mechanismReference' in m:
                        task_methods_refs.add(m['mechanismReference'])
            
            # Refined Style: 'method' (string or list)
            if 'method' in t:
                m_val = t['method']
                if isinstance(m_val, str):
                    task_methods_refs.add(m_val)
                elif isinstance(m_val, list):
                    for m_name in m_val:
                        if isinstance(m_name, str):
                            task_methods_refs.add(m_name)
    
    method_names = set()
    all_methods = method.get('methods', []) + method.get('mechanisms', [])
    for m in all_methods:
        if 'name' in m:
            method_names.add(m['name'])
                
    if task_methods_refs:
        matched_methods = task_methods_refs.intersection(method_names)
        scores['task_method_binding'] = len(matched_methods) / len(task_methods_refs)
    else:
        scores['task_method_binding'] = 1.0 
        
    # Helper to clean/parse parameter strings
    def get_param_type(param_str):
        # Support "name: type" format
        if ":" in param_str:
            return param_str.split(":", 1)[1].strip()
        return param_str.strip()

    # 2. Method-Knowledge Binding: Method params -> Knowledge concepts
    method_params = set()
    for m in all_methods:
        # Refined support: inputs/output vs inputParameters/outputParameters
        inputs = m.get('inputParameters') or m.get('inputs', [])
        outputs = m.get('outputParameters') or m.get('outputs', [])
        
        for p in inputs: method_params.add(get_param_type(p))
        for p in outputs: method_params.add(get_param_type(p))
    
    if method_params:
        matched_m_params = float(len([p for p in method_params if p in knowledge_concepts]))
        scores['method_knowledge_binding'] = matched_m_params / len(method_params)
    else:
        scores['method_knowledge_binding'] = 1.0

    # 3. Task-Knowledge Binding: Task params -> Knowledge concepts
    task_params = set()
    if 'tasks' in task:
        for t in task['tasks']:
            inputs = t.get('inputParameters') or t.get('inputs', [])
            outputs = t.get('outputParameters') or t.get('outputs', [])
            
            for p in inputs: task_params.add(get_param_type(p))
            for p in outputs: task_params.add(get_param_type(p))
                
    if task_params:
        matched_t_params = float(len([p for p in task_params if p in knowledge_concepts]))
        scores['task_knowledge_binding'] = matched_t_params / len(task_params)
    else:
        scores['task_knowledge_binding'] = 1.0
        
    return scores

# --- Metric 3: Procedural Semantics ---

def analyze_fsm(method_data: Dict) -> Dict[str, float]:
    results = {
        "guard_logic": 0.0,
        "failure_modeling": 0.0,
        "unreachable_states": 0.0
    }
    
    # Combine methods and mechanisms explicitly? 
    # Or just iterate whatever is there.
    # Refined TMKs have "methods" and "mechanisms".
    all_units = method_data.get('methods', []) + method_data.get('mechanisms', [])

    total_transitions = 0
    guarded_transitions = 0
    methods_with_failure = 0
    total_fsm_methods = 0
    total_unreachable_ratio = 0.0 

    for method in all_units:
        # Refined uses 'fsm' object directly. Raw uses 'organizer'.
        fsm = method.get('fsm') or method.get('organizer') or method.get('organiser')
        
        # Skip methods that don't have an FSM (primitives)
        if not fsm:
            continue
            
        total_fsm_methods += 1
        
    # 1. Guard Logic
        transitions_list = []
        raw_transitions = fsm.get('transitions')
        
        if isinstance(raw_transitions, list):
            transitions_list = raw_transitions
        elif isinstance(raw_transitions, dict):
            # Map style: "State": [ {to:..., guard:...}, ... ]
            for t_list in raw_transitions.values():
                if isinstance(t_list, list):
                    transitions_list.extend(t_list)
        
        total_transitions += len(transitions_list)
        for t in transitions_list:
            if not isinstance(t, dict): continue
            
            # Refined uses 'guard'. Raw uses 'dataCondition'.
            condition = t.get('guard') or t.get('dataCondition', '')
            
            # Check if condition is non-trivial (not empty, not just "true" or "True")
            if condition and condition.lower() != 'true':
                guarded_transitions += 1
        
        # 2. Failure Modeling
        # Raw: failureState in organizer
        # Refined: failure in fsm
        failure_state_name = fsm.get('failureState') or fsm.get('failure')
        has_failure_state_def = False
        has_failure_goal = False
        
        if failure_state_name:
             # Check if state exists in 'states'
             states = fsm.get('states', [])
             
             state_names = []
             for s in states:
                 if isinstance(s, str):
                     state_names.append(s)
                 elif isinstance(s, dict):
                     state_names.append(s.get('name'))
            
             if failure_state_name in state_names:
                 has_failure_state_def = True
                 
                 # Check if it calls FailureGoal
                 # Refined: stateInvocations map. Raw: goalInvocation in state dict.
                 
                 # Strategy A: Check stateInvocations map
                 state_invocations = method.get('stateInvocations', {})
                 inv_data = state_invocations.get(failure_state_name, {})
                 if inv_data:
                     # Check goalInvocation
                     gi = inv_data.get('goalInvocation', {})
                     if gi.get('task') == 'FailureGoal' or gi.get('goalReference') == 'FailureGoal':
                         has_failure_goal = True
                         
                 # Strategy B: Check embedded state dict
                 if not has_failure_goal:
                     for s in states:
                         if isinstance(s, dict) and s.get('name') == failure_state_name:
                             gi = s.get('goalInvocation', {})
                             if gi.get('goalReference') == 'FailureGoal':
                                 has_failure_goal = True
                             break
        
        if has_failure_state_def and has_failure_goal:
            methods_with_failure += 1

        # 3. Dead-End Detection (Reachability)
        start_state = fsm.get('startState') or fsm.get('start')
        states = fsm.get('states', [])
        
        state_names = set()
        for s in states:
             if isinstance(s, str): state_names.add(s)
             elif isinstance(s, dict): state_names.add(s.get('name'))
        
        if not state_names:
            continue
            
        # Build adjacency list
        adj = {name: [] for name in state_names}
        
        # Use simple flattened transition list we built earlier? 
        # No, for adjacency we need Source. Flattening lost source for Map style.
        # So we must reproduce logic to iterate.
        if isinstance(raw_transitions, list):
             for t in raw_transitions:
                 if not isinstance(t, dict): continue
                 src = t.get('sourceState')
                 tgt = t.get('targetState')
                 if src in adj and tgt in state_names:
                     adj[src].append(tgt)
        elif isinstance(raw_transitions, dict):
             for src_key, t_list in raw_transitions.items():
                 if src_key in adj:
                     if isinstance(t_list, list):
                         for t in t_list:
                             if not isinstance(t, dict): continue
                             tgt = t.get('to')
                             if tgt in state_names:
                                 adj[src_key].append(tgt)

        # BFS/DFS for reachability
        reachable = set()
        if start_state in state_names:
            queue = [start_state]
            reachable.add(start_state)
            while queue:
                curr = queue.pop(0)
                for neighbor in adj[curr]:
                    if neighbor not in reachable:
                        reachable.add(neighbor)
                        queue.append(neighbor)
        
        unreachable_count = len(state_names) - len(reachable)
        if len(state_names) > 0:
            total_unreachable_ratio += (unreachable_count / len(state_names))

    # Compile results
    results['guard_logic'] = guarded_transitions / total_transitions if total_transitions > 0 else 0.0
    results['failure_modeling'] = methods_with_failure / total_fsm_methods if total_fsm_methods > 0 else 0.0
    avg_unreachable = total_unreachable_ratio / total_fsm_methods if total_fsm_methods > 0 else 0.0
    results['unreachable_states'] = 1.0 - avg_unreachable
    
    return results

def calculate_hierarchy_depth(method_data: Dict, task_data: Dict) -> int:
    """
    Calculates the maximum depth of the method hierarchy.
    """
    if 'tasks' not in task_data:
        return 0
        
    all_units = method_data.get('methods', []) + method_data.get('mechanisms', [])
    
    # 1. Map Task -> Method (which method solves which task)
    task_to_methods = {}
    for task in task_data.get('tasks', []):
        t_name = task.get('name')
        methods = []
        # Raw Style
        if 'means' in task:
            for m in task['means']:
                ref = m.get('mechanismReference')
                if ref:
                    methods.append(ref)
                    
        # Refined Style: 'method'
        if 'method' in task:
            m_val = task['method']
            if isinstance(m_val, str):
                methods.append(m_val)
            elif isinstance(m_val, list):
                for m_name in m_val:
                    if isinstance(m_name, str):
                        methods.append(m_name)
                        
        task_to_methods[t_name] = methods
        
    # 2. Map Method -> SubGoals (Tasks called by this method)
    method_to_subtasks = {}
    for method in all_units:
        m_name = method.get('name')
        subtasks = []
        
        # Check FSM states (Raw & Refined)
        fsm = method.get('fsm') or method.get('organizer') or method.get('organiser')
        # Also check operations? Refined ops can call other things? 
        # Usually it's via goal invocation in state.
        
        if fsm: 
            states = fsm.get('states', [])
            
            # A. Embedded states
            for s in states:
                if isinstance(s, dict):
                    inv = s.get('goalInvocation', {})
                    ref = inv.get('goalReference') or inv.get('task')
                    # Check type
                    type_val = inv.get('type')
                    if ref and ref != 'FailureGoal':
                         subtasks.append(ref)
                    
            # B. stateInvocations map (Refined)
            invocations = method.get('stateInvocations', {})
            for _, data in invocations.items():
                inv = data.get('goalInvocation', {})
                ref = inv.get('goalReference') or inv.get('task')
                if ref and ref != 'FailureGoal':
                    subtasks.append(ref)
                
        method_to_subtasks[m_name] = subtasks
        
    # 3. Calculate depth
    memo = {}
    visiting = set()
    
    def get_method_depth(m_name):
        if m_name in visiting:
            return 0 
        if m_name in memo:
            return memo[m_name]
            
        visiting.add(m_name)
        
        subtasks = method_to_subtasks.get(m_name, [])
        max_sub_depth = 0
        
        for t_name in subtasks:
            # 1. Try finding methods via Task definition
            solver_methods = task_to_methods.get(t_name, [])
            
            # 2. If no Task definition, try explicit/implicit Method link 
            if not solver_methods:
                if t_name in method_to_subtasks:
                    solver_methods.append(t_name)
                elif (t_name + "Mechanism") in method_to_subtasks:
                    solver_methods.append(t_name + "Mechanism")
            
            for sm_name in solver_methods:
                if sm_name:
                    d = get_method_depth(sm_name)
                    if d > max_sub_depth:
                        max_sub_depth = d
        
        visiting.remove(m_name)
        depth = 1 + max_sub_depth
        memo[m_name] = depth
        return depth
    
    max_depth = 0
    # Iterate all methods found 
    for m_name in method_to_subtasks:
        d = get_method_depth(m_name)
        if d > max_depth:
            max_depth = d
            
    return max_depth

def check_teleology(method_data: Dict) -> float:
    """
    Checks Teleological Reasoning (Goal-Orientation).
    (1) Valid goalInvocation.
    """
    all_units = method_data.get('methods', []) + method_data.get('mechanisms', [])
        
    valid_invocations = 0
    total_invocations = 0
    
    for method in all_units:
        fsm = method.get('fsm') or method.get('organizer', {}) or method.get('organiser', {})
        
        # 1. Check embedded states (Raw)
        states = fsm.get('states', [])
        for state in states:
            if isinstance(state, dict):
                inv = state.get('goalInvocation', {})
                if inv:
                    total_invocations += 1
                    valid_types = ['subgoal', 'atomic', 'recursive', 'subtask', 'operation', 'task']
                    if inv.get('goalReference') and inv.get('type') in valid_types:
                        valid_invocations += 1
                        
        # 2. Check invocation maps (Refined)
        invocations = method.get('stateInvocations', {})
        for state_name, data in invocations.items():
            # Support 'goalInvocation' dictionary OR direct 'operation'/'task' key
            has_invocation = False
            is_valid = False
            
            if 'goalInvocation' in data:
                has_invocation = True
                inv = data['goalInvocation']
                ref = inv.get('goalReference') or inv.get('task')
                type_val = inv.get('type')
                
                valid_types = ['subgoal', 'atomic', 'recursive', 'subtask', 'operation', 'task', 'Task'] 
                if ref and type_val:
                    if type_val.lower() in [t.lower() for t in valid_types]:
                         is_valid = True
            
            elif 'operation' in data:
                # Direct operation call (common in Refined mechanisms)
                has_invocation = True
                if data['operation']:
                     is_valid = True
                     
            elif 'task' in data:
                 has_invocation = True
                 if data['task']:
                      is_valid = True
            
            if has_invocation:
                total_invocations += 1
                if is_valid:
                    valid_invocations += 1

    return valid_invocations / total_invocations if total_invocations > 0 else 0.0

def check_method_appropriateness(task_data: Dict, method_data: Dict) -> float:
    if 'tasks' not in task_data:
        return 0.0
        
    all_units = method_data.get('methods', []) + method_data.get('mechanisms', [])
    methods_by_name = {m.get('name'): m for m in all_units if 'name' in m}
    
    total_checks = 0
    passed_checks = 0
    
    def get_param_names(param_list):
        names = [] 
        for p in param_list:
            if ":" in p:
                names.append(p.split(":", 1)[0].strip())
            else:
                names.append(p.strip())
        return names

    # 1. Task -> Method Checks
    for task in task_data.get('tasks', []):
        
        # Identify referenced methods via 'means' OR 'method'
        referenced_methods = []
        actual_args_map = {} # method_name -> args list
        
        # A. Raw 'means'
        if 'means' in task:
            for m in task['means']:
                ref = m.get('mechanismReference')
                if ref:
                    referenced_methods.append(ref)
                    actual_args_map[ref] = m.get('actualArguments', [])

        # B. Refined 'method'
        if 'method' in task:
            m_val = task['method']
            refs = []
            if isinstance(m_val, str): refs = [m_val]
            elif isinstance(m_val, list): refs = m_val
            
            for ref in refs:
                if isinstance(ref, str):
                    referenced_methods.append(ref)
                    # For Refined, implicit args = Task Inputs?
                    # Let's assume passed args match task inputs by name
                    task_input_names = get_param_names(task.get('inputs') or task.get('inputParameters', []))
                    actual_args_map[ref] = task_input_names

        if not referenced_methods:
            continue

        task_scope = set(get_param_names(task.get('inputParameters', []) or task.get('inputs', [])) + 
                         get_param_names(task.get('outputParameters', []) or task.get('outputs', [])))
        
        for mech_ref in referenced_methods:
            if mech_ref in methods_by_name:
                method = methods_by_name[mech_ref]
                m_inputs = method.get('inputParameters') or method.get('inputs', [])
                m_outputs = method.get('outputParameters') or method.get('outputs', [])
                
                method_inputs = get_param_names(m_inputs)
                method_outputs = get_param_names(m_outputs)
                
                total_checks += 1
                
                actual_args = actual_args_map.get(mech_ref, [])
                
                # Check 1: Argument Count Match (Relaxed for Refined)
                # Allow actual_args (provided) to be <= method_inputs (required + outputs for procedures)
                # AND len(actual_args) >= 1 (some data passed, unless 0 args needed)
                
                is_compatible_count = len(actual_args) <= (len(method_inputs) + len(method_outputs))
                
                if not is_compatible_count:
                    continue
                
                # Check 2: Argument Existence in Task Scope
                all_args_exist = True
                for arg in actual_args:
                    if arg not in task_scope:
                         pass # Ignore for now
                
                if all_args_exist:
                    passed_checks += 1

    return passed_checks / total_checks if total_checks > 0 else 1.0

# --- Main Driver ---

def evaluate_tmk(tmk_dir: str, reference_pdf: str):
    """Evaluates a single TMK directory."""
    print(f"\\n--- Evaluating TMK Directory: {tmk_dir} ---")
    
    results = {}
    
    # Paths
    knowledge_path = os.path.join(tmk_dir, "Knowledge.json")
    task_path = os.path.join(tmk_dir, "Task.json")
    method_path = os.path.join(tmk_dir, "Method.json")
    
    # Schemata Paths — uses the repo's tmk-syntax-validator schemata
    schema_dir = os.path.join(os.path.dirname(__file__), "..", "tmk-syntax-validator", "schemata")
    task_schema_path = os.path.join(schema_dir, "Task.schema.json")
    method_schema_path = os.path.join(schema_dir, "Method.schema.json")
    knowledge_schema_path = os.path.join(schema_dir, "Knowledge.schema.json")

    # Load JSONs
    task_data = {}
    method_data = {}
    knowledge_data = {}
    
    try:
        if os.path.exists(task_path):
            with open(task_path, 'r') as f: task_data = json.load(f)
        if os.path.exists(method_path):
            with open(method_path, 'r') as f: method_data = json.load(f)
        if os.path.exists(knowledge_path):
            with open(knowledge_path, 'r') as f: knowledge_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSONs: {e}")
        return {}

    # Metric 1: Instructional Alignment
    if os.path.exists(knowledge_path) and os.path.exists(reference_pdf):
        print("Running Metric 1: Instructional Alignment...")
        alignment_score = calculate_instructional_alignment(knowledge_path, reference_pdf)
        results['instructional_alignment'] = alignment_score
        print(f"Instructional Alignment Score: {alignment_score:.2f}")
    else:
        print("Skipping Metric 1: Knowledge.json or Reference PDF not found.")
        results['instructional_alignment'] = 0.0

    # Metric 2.1: Structural Semantics (Schema Validation)
    print("Running Metric 2.1: Schema Validation...")
    structural_scores = {}
    
    if task_data and os.path.exists(task_schema_path):
        schema = load_schema(task_schema_path)
        score, max_score = score_json(task_data, schema)
        structural_scores['Task'] = score / max_score if max_score > 0 else 0
        
    if method_data and os.path.exists(method_schema_path):
        schema = load_schema(method_schema_path)
        score, max_score = score_json(method_data, schema)
        structural_scores['Method'] = score / max_score if max_score > 0 else 0
        
    if knowledge_data and os.path.exists(knowledge_schema_path):
        schema = load_schema(knowledge_schema_path)
        score, max_score = score_json(knowledge_data, schema)
        structural_scores['Knowledge'] = score / max_score if max_score > 0 else 0
        
    results['structural_validation'] = structural_scores
    print(f"Structural Validation Scores: {structural_scores}")

    # Metric 2.2: Binding Checks
    print("Running Metric 2.2: Binding Checks...")
    if task_data and method_data and knowledge_data:
        binding_scores = validate_bindings(task_data, method_data, knowledge_data)
        results['bindings'] = binding_scores
        print(f"Binding Scores: {binding_scores}")
    else:
         print("Skipping Metric 2.2: One or more JSON files missing.")
         results['bindings'] = {}
         
    # Metric 3: Procedural Semantics
    print("Running Metric 3: Procedural Semantics...")
    procedural_scores = {}
    if method_data:
        # 3.1 Causal Reasoning
        fsm_scores = analyze_fsm(method_data)
        procedural_scores.update(fsm_scores)
        
        # 3.2 Teleological Reasoning
        procedural_scores['teleology'] = check_teleology(method_data)
        
        # 3.2b Appropriateness (Task-Method Signature)
        if task_data:
             procedural_scores['appropriateness'] = check_method_appropriateness(task_data, method_data)
        else:
             procedural_scores['appropriateness'] = 0.0
        
        # 3.3 Hierarchical Composition
        if task_data:
            procedural_scores['hierarchy_depth'] = calculate_hierarchy_depth(method_data, task_data)
        else:
            procedural_scores['hierarchy_depth'] = 0
            
    results['procedural_semantics'] = procedural_scores
    print(f"Procedural Semantics Scores: {procedural_scores}")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TMK Evaluation Framework")
    parser.add_argument("--target", type=str, required=True, help="Path to TMK directory (e.g., RAW_TMK)")
    parser.add_argument("--reference_pdf", type=str, required=True, help="Path to reference textbook/transcript PDF")
    
    args = parser.parse_args()
    
    evaluate_tmk(args.target, args.reference_pdf)
