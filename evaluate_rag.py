import os
import asyncio
import pandas as pd
from datasets import Dataset 
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.language_models.chat_models import BaseChatModel
from dotenv import load_dotenv
load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- IMPORT YOUR ACTUAL BOT ---
try:
    from agents.desk_agent import run_router_agent 
    from agents.classification_agent import run_triage_agent
    from agents.specialist import run_specialist_agent
    from graph_agent import app as medical_graph
    from load_db import medical_db 
    print(" Connected to MediBot Brain.")
except ImportError as e:
    print(f" Error importing your bot: {e}")
    exit()

#  FIX 1: USE NEW MODEL (Llama 3 has been replaced by Llama 3.3)
#  FIX 2: FORCE n=1 (Groq crashes if n>1)
class GroqWrapper(ChatGroq):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if 'n' in kwargs:
            kwargs['n'] = 1 # Force single generation
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

judge_llm = GroqWrapper(model="llama-3.3-70b-versatile", temperature=0)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. DEFINE THE EXAM QUESTIONS
exam_questions = [
    {
        "question": "What are the symptoms of a heart attack?",
        "ground_truth": "Symptoms include chest pain, shortness of breath, and pain in the arm or jaw."
    },
    {
        "question": "How do I treat a first-degree burn?",
        "ground_truth": "Cool the burn with running water for 20 minutes. Do not use ice."
    },
    {
        "question": "What is hypertension?",
        "ground_truth": "Hypertension is high blood pressure, where the force of blood against artery walls is too high."
    }
]

# 3. HELPER FUNCTION: ASK YOUR BOT
def get_live_response(question):
    print(f" MediBot is thinking about: '{question}'...")
    try:
        intent = run_router_agent(question)
    except:
        intent = "SYMPTOM"

    response_text = ""

    if intent == "INFO":
        response_text = run_specialist_agent(f"Explain: {question}", {}, medical_db)
    elif intent == "SYMPTOM":
        session = {"age": "30", "history": []}
        triage = run_triage_agent(question, session)
        graph_inputs = { 
            "user_query": question, "patient_data": session, "triage_result": triage, 
            "diagnosis_draft": "", "treatment_draft": "", "skeptic_critique": "", 
            "skeptic_status": "", "revision_count": 0, "final_report": "" 
        }
        for output in medical_graph.stream(graph_inputs):
            for node, state in output.items():
                if node == "judge_agent":
                    response_text = state.get("final_report", "No report generated.")
    else:
        response_text = "I am a medical bot."

    return response_text

# 4. MAIN TEST LOOP
def run_live_test():
    print("------------------------------------------------")
    print(" STARTING LIVE EXAMINATION OF MEDIBOT")
    print("------------------------------------------------")

    generated_answers = []
    contexts = []

    # Step A: Get Answers
    for item in exam_questions:
        try:
            ans = get_live_response(item["question"])
            generated_answers.append(ans)
            contexts.append([item["ground_truth"]]) 
        except Exception as e:
            print(f" Error getting answer: {e}")
            generated_answers.append("Error")
            contexts.append(["Error"])

    # Step B: Build Dataset
    data = {
        'question': [q['question'] for q in exam_questions],
        'answer': generated_answers,
        'contexts': contexts,
        'ground_truth': [q['ground_truth'] for q in exam_questions]
    }
    
    dataset = Dataset.from_dict(data)

    # Step C: Grade
    print("\n Judge (Llama-3.3-70b) is grading...")
    
    try:
        results = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=judge_llm,
            embeddings=embeddings,
            raise_exceptions=False # Don't crash on single errors
        )

        print("\n FINAL REPORT CARD:")
        print(results)
        df = results.to_pandas()
        df.to_csv("live_test_results.csv", index=False)
        print(" Saved to live_test_results.csv")
        
    except Exception as e:
        print(f" RAGAS Error: {e}")
        # EMERGENCY BACKUP: If API fails, save raw answers so you have SOMETHING to show
        df = pd.DataFrame(data)
        df.to_csv("live_test_raw_backup.csv", index=False)
        print(" Saved raw answers to live_test_raw_backup.csv (Grading Failed)")

if __name__ == "__main__":
    run_live_test()