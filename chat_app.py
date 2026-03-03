import sys

from dotenv import load_dotenv
from load_db import medical_db 
from agents.desk_agent import run_router_agent
from agents.classification_agent import run_triage_agent
from agents.specialist import run_specialist_agent
from agents.skeptic import run_skeptic_agent
from agents.judge import run_judge_agent
from langchain_groq import ChatGroq
import os
load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
chat_llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.environ.get("GROQ_API_KEY"))

# --- SESSION MEMORY ---
session_state = {
    "patient_data": {
        "age": None,
        "history": [] ,
        "last_diagnosis": None
    },
    "step": "normal" # can be 'normal' or 'intake_age' or 'intake_history'
}

def process_input(user_input):
    # 1. HANDLE INTAKE (Same as before)
    if session_state["step"] == "intake_age":
        session_state["patient_data"]["age"] = user_input
        session_state["step"] = "intake_history"
        return "Got it. Now, do you have any medical history (Smoker, High BP, Diabetes)? If none, say 'None'."

    if session_state["step"] == "intake_history":
        session_state["patient_data"]["history"].append(user_input)
        session_state["step"] = "normal"
        return f"Profile Updated (Age: {session_state['patient_data']['age']}, History: {user_input}). Please describe your symptoms again."

    # 2. RUN ROUTER
    router_output = run_router_agent(user_input)
    category = router_output.get("category", "FOLLOW_UP") # Default to Follow-up if unsure
    print(f"   (🔍 Router identified: {category})")

    # 3. HANDLE CATEGORIES
    if category == "GREETING":
        return "Hello! I am Dr. AI. How can I help you today?"

    # --- NEW: HANDLE FOLLOW-UPS ---
    if category == "FOLLOW_UP":
        if session_state["last_diagnosis"]:
            # Contextual Chat: Answer using the previous diagnosis
            print("   💬 Answering follow-up using Context...")
            prompt = f"The user has a question about this diagnosis: '{session_state['last_diagnosis']}'. User Question: '{user_input}'. Answer briefly and helpfully."
            return chat_llm.invoke(prompt).content
        else:
            return "I need to understand your medical situation first. Please describe your symptoms."

    # --- HANDLE SYMPTOMS (THE COUNCIL) ---
    if category == "SYMPTOMS":
        has_age = session_state["patient_data"]["age"] is not None
        has_history = len(session_state["patient_data"]["history"]) > 0
        
        if not has_age or not has_history:
            session_state["step"] = "intake_age"
            return "To ensure your safety, I need to ask: How old are you?"
        
        else:
            print("\n🚨 ACTIVATING MEDICAL COUNCIL...")
            triage = run_triage_agent(user_input, session_state["patient_data"])
            specialist = run_specialist_agent(user_input, triage, vector_db=medical_db)
            skeptic = run_skeptic_agent(user_input, specialist, triage)
            final_response = run_judge_agent(user_input, specialist, skeptic, triage)
            
            # SAVE THE DIAGNOSIS TO MEMORY
            session_state["last_diagnosis"] = final_response 
            
            return final_response

    return "Could you clarify that? Are you describing a symptom?"
# --- MAIN LOOP ---
if __name__ == "__main__":
    print("==========================================")
    print("🏥 AI MEDICAL COUNCIL - ONLINE")
    print("   Type 'exit' to quit.")
    print("==========================================")

    while True:
        try:
            user_text = input("\n👤 YOU: ")
            if user_text.lower() in ["exit", "quit"]:
                print("👋 Exiting...")
                break
            
            # Run the logic
            response = process_input(user_text)
            
            print(f"\n🤖 AI: {response}")
            
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            break