import sys
import time
from load_db import medical_db
# Run - # python server.py #
# --- IMPORT ENGINES ---
try:
    # 1. The High-Risk Parallel Graph
    from graph_agent import app as medical_graph
    
    # 2. The Individual Agents (for Linear/Single modes)
    from agents.desk_agent import run_router_agent 
    from agents.classification_agent import run_triage_agent
    from agents.specialist import run_specialist_agent
    
    # We need the Judge manually for the Linear Tier
    # Ensure agents/judge.py has 'run_judge_agent' or 'run_judge'
    try:
        from agents.judge import run_judge_agent
    except ImportError:
        from agents.judge import run_judge_agent as run_judge

    print(" System Loaded: 3-Tier Architecture Ready.")

except ImportError as e:
    print(f" Critical Import Error: {e}")
    sys.exit(1)

# --- CONSOLE COLORS ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

def main_loop():
    print(Colors.HEADER + "\n --- NEURO-ORCHESTRATED MEDICAL COUNCIL (TIERED SYSTEM) ---" + Colors.ENDC)
    print("Type 'exit' to quit.\n")

    session = {
        "step": "normal", 
        "age": None, 
        "history": [],
        "main_complaint": None,
        "chat_history": []
    }

    while True:
        try:
            user_input = input(f"\n{Colors.BLUE}You: {Colors.ENDC}").strip()
        except KeyboardInterrupt:
            break
            
        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]: break

        # --- A. INTAKE FLOW ---
        if session["step"] == "intake_age":
            session["age"] = user_input
            session["step"] = "intake_history"
            print(f"{Colors.GREEN}Dr. AI:{Colors.ENDC} Got it. Medical history?")
            continue
        if session["step"] == "intake_history":
            session["history"] = [user_input]
            session["step"] = "normal"
            print(f"{Colors.GREEN}Dr. AI:{Colors.ENDC} Profile Set. Describe symptoms.")
            continue

        # --- B. ROUTER (Tier Selection) ---
        print(f"   Routing...", end="\r")
        
        # Hard Rule for Info
        if any(x in user_input.lower() for x in ["what is", "define", "explain", "causes of"]):
            category = "MEDICAL_INFO"
        else:
            try:
                router_out = run_router_agent(user_input)
                category = router_out.get("category", "SYMPTOMS")
            except:
                category = "SYMPTOMS"

        # --- TIER 1: INFORMATION (Single Agent) ---
        if category == "MEDICAL_INFO" or category == "GREETING":
            if category == "GREETING":
                print(f"{Colors.GREEN}Dr. AI:{Colors.ENDC} Hello! How can I help?")
                continue
                
            print(f"    [Tier 1] Single Agent Info Retrieval...")
            # Direct call, no overhead
            answer = run_specialist_agent(f"Define: {user_input}", {"risk_level": "INFO"}, medical_db)
            print(f"\n{Colors.GREEN}Dr. AI (Info):{Colors.ENDC}\n{answer}")
            continue

        # --- SYMPTOM HANDLING (Tier 2 vs Tier 3) ---
        if category == "SYMPTOMS":
            # 1. Intake Check
            if not session["age"]:
                session["step"] = "intake_age"
                print(f"{Colors.GREEN}Dr. AI:{Colors.ENDC} I need your age first.")
                continue
            
            # 2. Update Context
            if session["main_complaint"] is None:
                session["main_complaint"] = user_input
                print(f"    [Memory] Chief Complaint: {session['main_complaint']}")

            # 3. TRIAGE (The Decider)
            print(f"    Running Triage Risk Assessment...")
            try:
                triage_result = run_triage_agent(user_input, session)
                risk = triage_result.get("risk_level", "LOW").upper() # Default to LOW
            except:
                risk = "LOW"
                triage_result = {"risk_level": "LOW"}
            
            print(f"    Risk Level: {risk}")

            # --- PREPARE CONTEXT ---
            recent_history = session["chat_history"][-3:] 
            history_text = "\n".join([f"User: {msg}" for msg in recent_history])
            combined_query = f"""
            CHIEF COMPLAINT: {session['main_complaint']}
            RECENT HISTORY: {history_text}
            CURRENT UPDATE: {user_input}
            """

            # ============================================================
            # TIER 2: LOW RISK -> LINEAR CHAIN (No Graph, No Loop)
            # ============================================================
            if any(x in risk for x in ["LOW", "MILD", "MEDIUM"]):
                print(f"    [Tier 2] Low Risk Detected -> Activating Linear Chain")
                
                # Step 1: Specialist (Single Pass)
                print("    Specialist is thinking...")
                specialist_out = run_specialist_agent(combined_query, triage_result, medical_db)
                
                # Step 2: Judge (Formatting only, no Skeptic audit)
                print("    Judge is formatting...")
                final_response = run_judge_agent(combined_query, specialist_out, "No Critique (Low Risk)", triage_result)
                
                print(f"\n{Colors.GREEN}Dr. AI (Linear Report):{Colors.ENDC}")
                print(final_response)

            # ============================================================
            # TIER 3: HIGH RISK -> PARALLEL GRAPH (Council + Skeptic)
            # ============================================================
            else:
                print(f"    [Tier 3] High Risk Detected -> Activating Parallel Council")
                
                graph_inputs = {
                    "user_query": combined_query,
                    "patient_data": {"age": session["age"], "history": session["history"]},
                    "triage_result": triage_result,
                    "diagnosis_draft": "", "treatment_draft": "",
                    "skeptic_critique": "", "skeptic_status": "", "revision_count": 0, "final_report": ""
                }

                try:
                    final_state = medical_graph.invoke(graph_inputs)
                    print(f"\n{Colors.GREEN}Dr. AI (Council Report):{Colors.ENDC}")
                    print(final_state["final_report"])
                    
                    if final_state.get("revision_count", 0) > 0:
                        print(f"\n{Colors.WARNING}[System Log] Deep Reasoning Loop Triggered!{Colors.ENDC}")

                except Exception as e:
                    print(f" Graph Error: {e}")
            
            # Save history
            session["chat_history"].append(user_input)

if __name__ == "__main__":
    main_loop()