import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings 
# ^ If you used Google/OpenAI before, import that instead!

# 1. SETUP EMBEDDINGS (MUST MATCH YOUR ORIGINAL FILE)
# Did you use 'all-MiniLM-L6-v2' to create the DB? If yes, keep this:
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 2. DEFINE PATH TO YOUR SAVED FOLDER
# This matches the folder in your screenshot
DB_FAISS_PATH = "vectorstore/db_faiss"

def get_vector_db():
    print(f"📚 Loading Medical Vector Database from: {DB_FAISS_PATH}...")
    try:
        db = FAISS.load_local(
            folder_path=DB_FAISS_PATH, 
            embeddings=embeddings, 
            allow_dangerous_deserialization=True # Necessary for local pickle files
        )
        print("✅ Success! The Medical Knowledge Base is loaded.")
        return db
    except Exception as e:
        print(f"❌ Error loading DB: {e}")
        print("⚠️ HINT: Did you use a different embedding model (like Google or OpenAI) when you created these files?")
        return None

# Create a single instance to be imported elsewhere
medical_db = get_vector_db()