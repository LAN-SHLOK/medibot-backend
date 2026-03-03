import os
from urllib import response
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from load_db import medical_db
import time

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Use a smarter model (70b) for deep medical reasoning
class SafeChatGroq:
    def __init__(self, model_name):
        self.model_name = model_name
        self.api_key = os.getenv("GROQ_API_KEY")
        self._llm = ChatGroq(groq_api_key=self.api_key, model_name=model_name)

    def invoke(self, prompt):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Try to get the answer
                return self._llm.invoke(prompt)
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for Rate Limit (429) or Server Error (500, 503)
                if "429" in error_msg or "rate limit" in error_msg:
                    wait_time = 2 * (attempt + 1) # Wait 2s, then 4s...
                    print(f" Rate Limit Hit on {self.model_name}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                elif "500" in error_msg or "503" in error_msg:
                    print(f" Groq Server Error. Retrying...")
                    time.sleep(1)
                else:
                    # If it's a real code error, crash normally so you can fix it
                    raise e
        
        # If all retries fail, return a Backup Answer (The "Safety Net")
        return "System High Traffic. Please try again in 10 seconds."
llm=SafeChatGroq("llama-3.3-70b-versatile")
# --- THE EXPERT PERSONAS ---
# These act as "System Prompts" that we swap dynamically
PERSONAS = {
    "cardiologist": """
        ROLE: Senior Cardiologist. 
        EXPERTISE: Heart rhythm, hemodynamics, chest pain differential, ECG interpretation.
        FOCUS: Rule out life-threatening cardiac events (MI, Aortic Dissection).
    """,
    "neurologist": """
        ROLE: Neurologist.
        EXPERTISE: Central and peripheral nervous systems, stroke protocols, cranial nerves.
        FOCUS: Identify deficits in vision, speech, motor control, or sensation.
    """,
    "orthopedist": """
        ROLE: Orthopedic Surgeon.
        EXPERTISE: Musculoskeletal system, fractures, ligaments, range of motion.
        FOCUS: Mechanical injury vs. systemic pain.
    """,
    "dermatologist": """
        ROLE: Dermatologist.
        EXPERTISE: Skin pathology, rashes, lesions.
        FOCUS: Visual description and symptom timeline.
    """,
    "generalist": """
        ROLE: General Practitioner (GP).
        EXPERTISE: Primary care, common infections, triage of unclear symptoms.
        FOCUS: Holistic assessment.
    """
}

def run_specialist_agent(user_query, triage_result, vector_db=medical_db):
    """
    The Specialist Agent:
    1. Adopts the correct Persona (from Triage).
    2. Searches the Vector DB (RAG) for medical protocols.
    3. Drafts a detailed clinical response.
    """
    
    # 1. SETUP INPUTS
    specialist_type = triage_result.get("specialist", "generalist").lower()
    risk_level = triage_result.get("risk_level", "Unknown")
    red_flags = triage_result.get("red_flags", [])
    
    # Default to Generalist if the Triage output sends a weird string
    current_persona = PERSONAS.get(specialist_type, PERSONAS["generalist"])

    print(f" [Tier 2] {specialist_type.upper()} is active. (Risk: {risk_level})")

    # 2. RAG RETRIEVAL (The "Research" Phase)
    rag_context = "No internal medical documents available. Using general knowledge."
    
    if vector_db:
        print(f"   Searching Knowledge Base for: '{user_query}'...")
        try:
            # We search for the user's query to find relevant PDF chunks
            docs = vector_db.similarity_search(user_query, k=3)
            if docs:
                rag_context = "\n\n".join([d.page_content for d in docs])
                print(f"    Found {len(docs)} relevant context chunks.")
            else:
                print("    No relevant documents found in DB.")
        except Exception as e:
            print(f"    DB Search Failed: {e}")

    # 3. GENERATE DIAGNOSIS (The "Thinking" Phase)
    specialist_prompt = PromptTemplate(
        template="""<|system|>
        {persona_text}
        
        TASK:
        You are a Specialist Consultant. Analyze the patient query using the Context provided.
        
        INSTRUCTIONS:
        1. Review the "Retrieved Context" (Medical Guidelines).
        2. If the answer is in the Context, CITE IT.
        3. If the answer is NOT in the Context, use your general medical training but state: "Based on general protocols..."
        4. Address the specific "Red Flags" identified by Triage.
        
        RETRIEVED CONTEXT (FROM DATABASE):
        {context}
        
        TRIAGE REPORT:
        - Risk Level: {risk}
        - Red Flags: {flags}
        
        <|user|>
        Patient Query: {query}
        </s>
        <|assistant|>
        """,
        input_variables=["persona_text", "context", "risk", "flags", "query"]
    )

 
    formatted_prompt = specialist_prompt.invoke({
    "persona_text": current_persona,
    "context": rag_context,
    "risk": risk_level,
    "flags": ", ".join(red_flags),
    "query": user_query
})

# 2. Run the Safe LLM
# This calls your wrapper which handles the 429 Rate Limit
    ai_message = llm.invoke(formatted_prompt)

# 3. Parse the Output
# Extracts the string text from the AI message
    response = StrOutputParser().invoke(ai_message)

    return response