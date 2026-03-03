import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import time

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# We use the same smart model (70b) but with a "Critical" persona
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
def run_skeptic_agent(user_query, specialist_response, triage_result):
    """
    The Skeptic Agent:
    1. Reads the Specialist's diagnosis.
    2. Checks for "Blind Spots" or "Confirmation Bias".
    3. Proposes an alternative explanation (Differential Diagnosis).
    """
    
    print(" [Tier 3] The Skeptic is reviewing the case...")

    skeptic_prompt = PromptTemplate(
        template="""<|system|>
        You are a Medical Safety Auditor (The "Dr. House" Persona).
        Your ONLY job is to critique the Specialist's diagnosis to prevent errors.
        
        INPUTS:
        - Patient Query: {query}
        - Specialist's Opinion: {specialist_response}
        - Triage Risk Level: {risk}
        
        YOUR TASK:
        1. Identify any "Red Flags" the specialist might have minimized.
        2. Propose 1 Alternative Diagnosis (Differential Diagnosis). 
           (e.g., If Specialist said "Migraine", you ask "Could it be a Stroke?")
        3. Be brief, critical, and direct. Start with "REVIEW:".
        Review the diagnosis.
        4. If it is safe, start with "STATUS: APPROVE".
        5. If it is dangerous or wrong, start with "STATUS: REJECT". Also provied the reason for rejection and your alternative diagnosis for the specialist to consider
        
        CRITICAL RULE:
        - Write in ENGLISH ONLY.
        
        </s>
        <|assistant|>
        """,
        input_variables=["query", "specialist_response", "risk"]
    )
    
    formatted_prompt = skeptic_prompt.invoke({
        "specialist_response": specialist_response,
        "query": user_query,
        "risk": str(triage_result)
    })

    # 2. Run the Safe LLM
    ai_message = llm.invoke(formatted_prompt)

    # 3. Parse the Output
    # Check if we got a string back (Error message) or a message object
    if isinstance(ai_message, str):
        return ai_message
    
    critique = StrOutputParser().invoke(ai_message)
    
    return critique