import os
import requests
import json
import asyncio
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# --- CONFIGURATION ---
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_NAME = "phi3" 

# ==========================================
# 🟢 DATA STRUCTURE 2: MANUAL DEQUE
# ==========================================
class ChatHistoryDeque:
    """
    A manual fixed-size queue for chat history.
    Implements FIFO (First-In-First-Out) logic manually.
    """
    def __init__(self, capacity=6):
        self.capacity = capacity
        self.items = []

    def push(self, item):
        """Add item. If full, remove the oldest one."""
        self.items.append(item)
        if len(self.items) > self.capacity:
            self.items.pop(0) 

    def get_list(self):
        return self.items

class DoctorBrain:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.abspath(os.path.join(current_dir, "..", "vectorstore", "db_faiss"))
        
        # 🟢 Use Custom Data Structure
        self.chat_history = ChatHistoryDeque(capacity=6) 
        self.last_search_context = "" 

        try:
            self.vector_db = FAISS.load_local(
                self.db_path, 
                self.embeddings, 
                allow_dangerous_deserialization=True
            )
            print("✅ Database Loaded! (With Memory)")
        except Exception as e:
            print(f"❌ Error loading FAISS: {e}")
            self.vector_db = None

    def get_doctor_response(self, user_text):
        # --- A. SMART SEARCH LOGIC ---
        search_query = user_text
        if len(user_text.split()) < 5 and self.last_search_context:
            search_query = f"{self.last_search_context} {user_text}"
        
        self.last_search_context = user_text

        # --- B. RETRIEVAL (RAG) ---
        rag_context = "No specific records found."
        if self.vector_db:
            docs = self.vector_db.similarity_search(search_query, k=2)
            if docs:
                rag_context = "\n".join([doc.page_content for doc in docs])

        # 🟢 Update Memory using Manual Deque
        self.chat_history.push({"role": "user", "content": user_text})

        # --- C. SYSTEM PROMPT ---
        system_msg = {
            "role": "system",
            "content": f"""
            You are a Doctor.
            MEDICAL DATA:
            {rag_context}
            INSTRUCTIONS:
            - Answer using the MEDICAL DATA.
            - Keep answers spoken, natural, and short (max 2 sentences).
            """
        }

        # Convert Deque to list for API
        messages_to_send = [system_msg] + self.chat_history.get_list()

        # --- D. GENERATION ---
        try:
            response = requests.post('http://localhost:11434/api/chat', json={
                "model": MODEL_NAME,
                "messages": messages_to_send,
                "stream": False
            })
            reply = response.json()['message']['content']
            
            # 🟢 Save AI reply to Deque
            self.chat_history.push({"role": "assistant", "content": reply})
            
            return reply

        except Exception as e:
            return f"Brain Error: {e}"

def get_brain():
    return DoctorBrain()