import os
from typing import TypedDict
from langgraph.graph import StateGraph, END

# --- 1. CONNECT TO YOUR AGENTS ---
try:
    from load_db import medical_db
    # Using your EXACT file structure
    from agents.specialist import run_specialist_agent
    from agents.skeptic import run_skeptic_agent
    from agents.judge import run_judge_agent
except ImportError as e:
    # Safety Mock for imports
    print(f" [Graph] Import Warning: {e}")
    medical_db = None
    def run_specialist_agent(q, *args, **kwargs): return f"[Mock Analysis] {q}"
    def run_skeptic_agent(q, d, *args, **kwargs): return "STATUS: APPROVE"
    def run_judge_agent(*args, **kwargs): return "Final Report."

# --- 2. DEFINE STATE ---
class MedicalState(TypedDict):
    user_query: str
    patient_data: dict
    triage_result: dict
    
    # PARALLEL TRACKS
    diagnosis_draft: str   
    treatment_draft: str   
    
    # SHARED
    skeptic_critique: str
    skeptic_status: str
    revision_count: int
    final_report: str

# --- 3. DEFINE NODES ---
def node_diagnosis(state: MedicalState):
    print("    [Parallel] Dr. Diagnosis is analyzing pathology...")
    context = "ROLE: Diagnostic Expert. TASK: Identify condition. CONSTRAINT: No meds."
    if state.get("skeptic_critique"): context += f"\nPREVIOUS ERROR: {state['skeptic_critique']}"
    
    query = f"{state['user_query']}\nCONTEXT: {context}"
    result = run_specialist_agent(query, state["triage_result"], vector_db=medical_db)
    return {"diagnosis_draft": result}

def node_treatment(state: MedicalState):
    print("   [Parallel] Dr. Treatment is planning care...")
    context = "ROLE: Treatment Expert. TASK: Suggest meds/safety. CONSTRAINT: Focus on safety."
    if state.get("skeptic_critique"): context += f"\nPREVIOUS ERROR: {state['skeptic_critique']}"

    query = f"{state['user_query']}\nCONTEXT: {context}"
    result = run_specialist_agent(query, state["triage_result"], vector_db=medical_db)
    return {"treatment_draft": result}

def node_skeptic_merger(state: MedicalState):
    print("    [Skeptic] Merging & Reviewing Parallel Reports...")
    full_text = f"DIAGNOSIS:\n{state.get('diagnosis_draft')}\n\nTREATMENT:\n{state.get('treatment_draft')}"
    critique = run_skeptic_agent(state["user_query"], full_text, state["triage_result"])
    status = "REJECT" if "REJECT" in critique.upper() else "APPROVE"
    return {"skeptic_critique": critique, "skeptic_status": status, "revision_count": state.get("revision_count", 0) + 1}

def node_judge(state: MedicalState):
    print("   [Judge] Finalizing Report...")
    combined = f"{state['diagnosis_draft']}\n{state['treatment_draft']}"
    final = run_judge_agent(state['user_query'], combined, state['skeptic_critique'], state['triage_result'])
    return {"final_report": final}

# --- 4. WIRING THE GRAPH ---
workflow = StateGraph(MedicalState)
workflow.add_node("Dr_Diagnosis", node_diagnosis)
workflow.add_node("Dr_Treatment", node_treatment)
workflow.add_node("Skeptic", node_skeptic_merger)
workflow.add_node("Judge", node_judge)

# Parallel Dispatcher
def node_dispatcher(state): return {}
workflow.add_node("Dispatcher", node_dispatcher)
workflow.set_entry_point("Dispatcher")

# Fan-Out
workflow.add_edge("Dispatcher", "Dr_Diagnosis")
workflow.add_edge("Dispatcher", "Dr_Treatment")

# Fan-In
workflow.add_edge("Dr_Diagnosis", "Skeptic")
workflow.add_edge("Dr_Treatment", "Skeptic")

# Loop Logic
def skeptic_logic(state):
    if state["skeptic_status"] == "REJECT" and state["revision_count"] < 3:
        print("   [Loop] Skeptic Rejected. Retrying...")
        return "Dispatcher"
    return "Judge"

workflow.add_conditional_edges("Skeptic", skeptic_logic, {"Dispatcher": "Dispatcher", "Judge": "Judge"})
workflow.add_edge("Judge", END)

app = workflow.compile()