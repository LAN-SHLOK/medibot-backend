# main_flow.py
import time
from agents.classification_agent import run_triage_agent
from agents.specialist import run_specialist_agent
from agents.skeptic import run_skeptic_agent
from agents.judge import run_judge_agent
from load_db import medical_db
from agents.desk_agent import run_router_agent

# --- SIMULATED SESSION MEMORY ---
# In a real app, this sits in the browser or database.
# We start EMPTY.
session_state = {
    "patient_data": {
        "age": None,
        "history": [] 
    }
}

# --- DUMMY DATA FOR TESTING ---
# Scenario: User describes a "Silent Heart Attack" (Indigestion + Jaw Pain)
user_query = "I have a deep, dull ache in my mid-back on the right side. I also have a fever and my pee looks cloudy."
patient_data = {"age": 55, "history": ["Smoker", "High BP"]}

print("="*60)
print(f" PATIENT: '{user_query}'")
print("="*60)

start_time = time.time()

# 1️ TIER 1: TRIAGE (The Router)
triage_result = run_triage_agent(user_query, patient_data)
print(f"\n🚦 TIER 1 DECISION: {triage_result.get('specialist').upper()} (Risk: {triage_result.get('risk_level')})")

# 2️ TIER 2: SPECIALIST (The Doctor)
# (Pass 'vector_db=None' for this test, but in real app pass your DB)
specialist_draft = run_specialist_agent(user_query, triage_result, vector_db=None)
print(f"\n TIER 2 DRAFT:\n{specialist_draft[:200]}...") # Printing first 200 chars only

# 3️ TIER 3: SKEPTIC (The Auditor)
skeptic_review = run_skeptic_agent(user_query, specialist_draft, triage_result)
print(f"\n TIER 3 REVIEW:\n{skeptic_review}")

# 4️ TIER 4: JUDGE (The Voice)
final_response = run_judge_agent(user_query, specialist_draft, skeptic_review, triage_result)

end_time = time.time()

print("\n" + "="*60)
print(" FINAL OUTPUT TO PATIENT:")
print(final_response)
print("="*60)
print(f"⏱ Total Time: {round(end_time - start_time, 2)} seconds")





def handle_user_message(user_query):
    print(f"\n💬 USER: '{user_query}'")
    
    # --- STEP 1: FRONT DESK (TIER 0) ---
    router_decision = run_router_agent(user_query, session_state["patient_data"])
    action = router_decision.get("action", "GENERAL")
    
    print(f"🚦 ROUTER DECISION: {action}")

    # --- PATH A: GREETING / GENERAL ---
    if action == "GREETING":
        return "Hello! I am your AI Medical Council. How can I help you today?"
        
    if action == "GENERAL":
        return "That is a general medical question. [You can route this to a simple RAG search here]."

    # --- PATH B: INTAKE (Gathering Info) ---
    if action == "INTAKE":
        # Simple logic to fill the missing data
        # In a real app, you would ask one by one. Here we simulate the AI asking.
        return "I noticed you have symptoms. To give you a safe diagnosis, I need to know: \n1. What is your age? \n2. Do you have any medical history (Smoker, BP, Diabetes)?"

    # --- PATH C: THE COUNCIL (Only runs if we have data + symptoms) ---
    if action == "COUNCIL":
        print("🚨 ACTIVATING MEDICAL COUNCIL...")
        
        # 1. Triage
        triage_result = run_triage_agent(user_query, session_state["patient_data"])
        
        # 2. Specialist
        specialist_draft = run_specialist_agent(user_query, triage_result, vector_db=medical_db)
        
        # 3. Skeptic
        skeptic_review = run_skeptic_agent(user_query, specialist_draft, triage_result)
        
        # 4. Judge
        final_response = run_judge_agent(user_query, specialist_draft, skeptic_review, triage_result)
        
        return final_response

# ==========================================
# 🧪 TEST SIMULATION (Conversation Flow)
# ==========================================

# Turn 1: User says Hi (Should NOT trigger Council)
print(handle_user_message("Hello there"))

# Turn 2: User mentions pain (Should trigger INTAKE, because data is empty)
print(handle_user_message("I have a bad headache"))

# Turn 3: User provides info (We manually update state to simulate user answering)
print("\n[User provides info... Updating System Memory]")
session_state["patient_data"]["age"] = 30
session_state["patient_data"]["history"] = ["Migraines"]

# Turn 4: User asks again (Should NOW trigger Council)
print(handle_user_message("I have a bad headache"))