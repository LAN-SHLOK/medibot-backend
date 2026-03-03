import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import time

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# We use a higher temperature (0.3) for a warmer, more human tone
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
                    print(f"⚠️ Rate Limit Hit on {self.model_name}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                elif "500" in error_msg or "503" in error_msg:
                    print(f"⚠️ Groq Server Error. Retrying...")
                    time.sleep(1)
                else:
                    # If it's a real code error, crash normally so you can fix it
                    raise e
        
        # If all retries fail, return a Backup Answer (The "Safety Net")
        return "System High Traffic. Please try again in 10 seconds."
llm=SafeChatGroq("llama-3.3-70b-versatile")
def run_judge_agent(user_query, specialist_response, skeptic_review, triage_result):
    """
    The Judge Agent:
    1. Reads the Specialist's Draft.
    2. Reads the Skeptic's Critique.
    3. Decides what is safe to tell the patient.
    4. Formats the final output.
    """
    
    print(" [Tier 4] The Judge is finalizing the report...")
    
    judge_prompt = PromptTemplate(
        template="""<|system|>
        You are the Chief Medical Officer.
        
        TASK:
        Synthesize the medical debate into a FINAL RESPONSE for the patient.
        
        THE DEBATE:
        - Specialist Said: {specialist_response}
        - Skeptic Argued: {skeptic_review}
        - Risk Level: {risk}
        
        GUIDELINES:
        1. Be Empathetic and Professional (Warm tone).
        2. If the Skeptic raised a valid safety concern (High Risk), include it gently.
        3. Do NOT mention "The Skeptic" or "The Specialist" to the user. Speak as "We" or "I".
        4. Structure:
           - Empathize with symptoms.
           - Explanation of possible causes.
           - Clear Next Steps (e.g., "See a doctor", "Rest").
        
        CRITICAL RULE:
        - ANSWER IN ENGLISH ONLY.
        
        <|user|>
        Patient Query: {query}
        </s>
        <|assistant|>
        """,
        input_variables=["specialist_response", "skeptic_review", "risk", "query"]
    )
    
    formatted_prompt = judge_prompt.invoke({
        "query": user_query,                 # Map 'user_query' arg -> '{query}' slot
        "specialist_response": specialist_response,
        "skeptic_review": skeptic_review,    # Map 'skeptic_review' arg -> '{skeptic_review}' slot
        "risk": str(triage_result)           # Map 'triage_result' arg -> '{risk}' slot
    })

    # 2. Run the Safe LLM
    ai_message = llm.invoke(formatted_prompt)

    # 3. Parse the Output
    final_verdict = StrOutputParser().invoke(ai_message)

    return final_verdict