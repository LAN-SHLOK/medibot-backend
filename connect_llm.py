# import os
# from langchain_groq import ChatGroq
# from langchain_community.vectorstores import FAISS
# from langchain_huggingface import HuggingFaceEmbeddings
# # Using the classic chains as you requested
# from langchain_classic.chains.retrieval import create_retrieval_chain
# from langchain_classic.chains.combine_documents import create_stuff_documents_chain
# from langchain_core.prompts import PromptTemplate
# from dotenv import load_dotenv

# from database_manager import init_db, save_message, get_chat_history

# # 1. Setup Environment
# load_dotenv()
# GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# GROQ_MODEL_NAME = "llama-3.1-8b-instant"

# init_db()
# CURRENT_SESSION_ID = "default_session"

# llm = ChatGroq(
#     model=GROQ_MODEL_NAME,
#     temperature=0.3, # Lower temperature is better for medical facts
#     max_tokens=512,
#     api_key=GROQ_API_KEY,
# )

# # 2. Load Database
# DB_FAISS_PATH = "vectorstore/db_faiss"
# embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
# db = FAISS.load_local(DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True)

# # 3. Build Prompt (FIXED VARIABLES)
# report_template = """<|system|>
# You are Medibot, a friendly and empathetic medical assistant. 
# Your goal is to have a natural, human-like conversation with the user, just like a real doctor would.

# INSTRUCTIONS:
# 1. **Be Conversational First:** - Start with a warm, natural response. Acknowledge what the user said.
#    - If the user asks a simple follow-up (e.g., "Which mosquito?", "Is it contagious?"), answer directly and conversationally. Do NOT use bullet points or headers for simple chat.
   
# 2. **Use Structure Only When Needed:**
#    - ONLY provide the "Medical Report" (Medicines/Dos/Don'ts) if the user asks for a **Treatment**, **Diagnosis**, or **Diet Plan**.
#    - If you do provide a report, keep the tone warm, not robotic.

# 3. **Context Awareness:**
#    - Use the 'Chat History' to understand what "it" or "that" refers to.
#    - If the answer is not in the context, say "I'm not sure about that specific detail based on my medical notes, but typically..." (be honest but helpful).

# CRITICAL INSTRUCTIONS:
# 1. ANSWER ONLY IN ENGLISH. 
# 2. Do not use Russian, Cyrillic, or any other language.
# 3. Answer simple questions directly.
# 4. Use "Medical Report" structure ONLY for specific treatments/diagnoses.
# 5. Use Chat History for context.

# Medical Report Structure (Use ONLY for treatments/diagnoses):
# ---
# **MEDICINES & DOSAGE:** [List if found]
# **DO'S:** [List helpful actions]
# **DON'TS:** [List avoidances]
# ---

# Context:
# {context}

# Chat History:
# {chat_history}

# User Question: 
# {input} 
# </s>
# <|assistant|>
# """
# # Note: Changed {question} to {input} above to match the chain's expectation

# PROMPT = PromptTemplate(
#     template=report_template,
#     input_variables=["context", "chat_history", "input"] # <--- Updated
# )

# # 4. Create Chains
# combine_docs_chain = create_stuff_documents_chain(llm, PROMPT)

# rag_chain = create_retrieval_chain(
#     db.as_retriever(search_kwargs={'k': 1}), 
#     combine_docs_chain
# )



# def format_chat_history(history):
#     """
#     Converts list of tuples: [("Hi", "Hello"), ("What is fever?", "Fever is...")]
#     Into a string: 
#     "Human: Hi
#      AI: Hello
#      Human: What is fever?
#      AI: Fever is..."
#     """
#     formatted_str = ""
#     for user_msg, ai_msg in history:
#         formatted_str += f"Human: {user_msg}\nAI: {ai_msg}\n"
#     return formatted_str

# # 5. Run (Continuous Chat Loop)
# if __name__ == "__main__":
#     print("="*40)
#     print(f"Medibot is ready for {CURRENT_SESSION_ID}. (Type 'exit' to stop)")
#     print("="*40)
#     chat_history = []
#     chat_history = get_chat_history(CURRENT_SESSION_ID)
#     if chat_history:
#         print(f"\n[System] Loaded {len(chat_history)} past exchanges from database.")
#         # Print the last exchange so user knows where they left off
#         last_user, last_ai = chat_history[-1]
#         print(f"Last Interaction -> You: {last_user} | Dr: {last_ai[:50]}...")
#     else:
#         print("\n[System] Starting new patient session.")

#     # Initialize empty history list


#     while True:
#         user_query = input("\nYou: ")
        
#         if user_query.lower() in ["exit", "quit"]:
#             break

#         # 1. Save User Query to SQL
#         save_message(CURRENT_SESSION_ID, "user", user_query)

#         # 2. Prepare History String
#         history_str = format_chat_history(chat_history)

#         # 3. Get Response
#         response = rag_chain.invoke({
#             'input': user_query,
#             'chat_history': history_str
#         })
#         answer = response["answer"]

#         # 4. Save AI Response to SQL
#         save_message(CURRENT_SESSION_ID, "assistant", answer)

#         # 5. Update local list (so immediate follow-ups work)
#         chat_history.append((user_query, answer))

#         print(f"Medibot : {answer}")