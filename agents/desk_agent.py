import os
import pickle
from sentence_transformers import SentenceTransformer

# --- LOAD YOUR TRANSFER LEARNING ROUTER ---
current_dir = os.path.dirname(os.path.abspath(__file__))
nn_path = os.path.join(current_dir, "..", "router_nn.pkl")

try:
    # 1. Load the Sentence Embedder (Semantic feature extractor)
    embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    # 2. Load your custom trained MLP Neural Network
    with open(nn_path, "rb") as f:
        nn_model = pickle.load(f)
        
    print(" Semantic Neural Network Router Loaded Successfully!")
except Exception as e:
    print(f" Warning: Could not load custom NN. Error: {e}")
    embedder, nn_model = None, None

def run_router_agent(user_query):
    if not embedder or not nn_model:
        return "SYMPTOM" 

    try:
        # 1. Convert the user's unseen text into a 384-dimension semantic vector
        X_input = embedder.encode([user_query.lower()])
        
        # 2. Feed the vector through your Neural Network
        prediction = nn_model.predict(X_input)[0]
        
        print(f" [Semantic NN Router] Classified '{user_query}' -> {prediction}")
        return prediction

    except Exception as e:
        print(f"NN Router Error: {e}")
        return "SYMPTOM"