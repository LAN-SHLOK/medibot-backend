import os
import json
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# Use a slightly smarter model for medical triage if possible, 
# but 8b-instant works if prompted correctly.
llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile" # Switched to 70B for better medical safety
)

def run_triage_agent(user_query, session_data):
    """
    Analyzes the SYMPTOM to determine Risk Level.
    Returns a Dictionary: {"risk_level": "HIGH", "reasoning": "..."}
    """
    
    triage_template = """<|system|>
    You are an Emergency Triage Nurse.
    
    TASK: Analyze the patient's complaint and assign a Risk Level.
    
    RISK LEVELS:
    - HIGH: Chest pain, difficulty breathing, stroke signs (face drooping, arm weakness), severe trauma, suicide ideation, crushing pain, unconsciousness.
    - MEDIUM: High fever (>103F), broken bones, deep cuts, persistent vomiting, severe migraine.
    - LOW: Mild headache, cold/flu, sore throat, skin rash, minor bruises, anxiety.

    PATIENT CONTEXT:
    - Age: {age}
    - Medical History: {history}
    - Complaint: {query}

    OUTPUT FORMAT (JSON ONLY):
    {{
        "reasoning": "One sentence explaining why you chose this risk level.",
        "category": "Cardiology / Neurology / General / etc.",
        "risk_level": "HIGH / MEDIUM / LOW"
    }}
    </s>
    <|user|>
    Analyze this case.
    </s>
    <|assistant|>
    """

    triage_prompt = PromptTemplate(template=triage_template, input_variables=["query", "age", "history"])

    try:
        # 1. Format and Run
        formatted = triage_prompt.invoke({
            "query": user_query,
            "age": session_data.get("age", "Unknown"),
            "history": session_data.get("history", "None")
        })
        
        response_text = llm.invoke(formatted).content
        
        # 2. Extract JSON safely
        # Sometimes models add text before/after the JSON. We grab everything between { and }.
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
            triage_dict = json.loads(clean_json)
        else:
            raise ValueError("No JSON found in response")

        # 3. SAFETY OVERRIDE (Hard Rules)
        # Even if AI says Low, we force High for key words
        reasoning_lower = triage_dict.get("reasoning", "").lower() + user_query.lower()
        danger_words = ["chest pain", "heart attack", "stroke", "can't breathe", "suicide", "crushing"]
        
        if any(word in reasoning_lower for word in danger_words):
            if triage_dict["risk_level"] != "HIGH":
                print(" SAFETY NET: Upgrading Risk to HIGH based on keywords.")
                triage_dict["risk_level"] = "HIGH"

        return triage_dict

    except Exception as e:
        print(f" Triage Error: {e}")
        # Fail Safe: If we can't decide, assume MEDIUM risk to be safe.
        return {
            "risk_level": "MEDIUM",
            "category": "General",
            "reasoning": "System error during triage. Defaulting to safe mode."
        }