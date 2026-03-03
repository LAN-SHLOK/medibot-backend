import pickle
from sentence_transformers import SentenceTransformer
from sklearn.neural_network import MLPClassifier

print("🧠 Loading Pre-trained Transformer (Transfer Learning)...")
# We use the exact same embedding model you use for your RAG database!
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# 1. The Smarter Dataset
# 1. The Comprehensive Training Dataset
texts = [
    # ==========================================
    # GREETINGS
    # ==========================================
    "hello", "hi", "hey medibot", "good morning", "greetings", "wake up system",
    
    # ==========================================
    # TIER 3: SEVERE SYMPTOMS -> Routes to LangGraph 
    # ==========================================
    # Cardiac / Respiratory / Neuro / Trauma
    "i have severe chest pain", "crushing pressure in my chest", "i can't breathe", 
    "gasping for air", "my heart is beating too fast and it hurts",
    "worst headache of my life", "sudden blurry vision", "half my face is drooping", 
    "i feel numb on my left side", "slurred speech", "patient is unconscious", "seizure",
    "deep cut and won't stop bleeding", "bone is sticking out", "gunshot wound", "vomiting blood",
    
    # ==========================================
    # TIER 2: MODERATE SYMPTOMS -> Routes to Linear Multi-Agent
    # ==========================================
    # General sickness / Moderate pain / Infections
    "i have a fever of 101", "my stomach hurts a lot after eating", "i feel very nauseous",
    "i sprained my ankle and it is swollen", "moderate back pain", "i have a bad cough",
    "ear infection symptoms", "painful urination", "i threw up twice today",
    "my throat is incredibly sore", "i think i have the flu", "persistent diarrhea",
    
    # ==========================================
    # TIER 1: MILD INFO & GENERAL -> Routes to Single Agent
    # ==========================================
    # Minor Skin / Hair / Diet / General Knowledge
    "i have mild acne on my face especially cheeks", "how to cure pimples", 
    "dry scalp and dandruff", "hair loss remedies", "small paper cut", "mild sunburn", 
    "small rash on my arm", "runny nose and sneezing", "stuffy nose",
    "what are the side effects of whey protein", "is creatine safe to take daily", 
    "how to lose belly fat", "muscle soreness after workout", "best diet for weight loss", 
    "what is cancer", "explain ibuprofen", "how many bones in the human body", 
    "define diabetes", "what causes high blood pressure", "symptoms of pcos",
    
    # ==========================================
    # EXIT PROTOCOLS
    # ==========================================
    "bye", "thank you", "goodbye", "exit", "stop generation", "see you later",
    
    # ==========================================
    # GENERAL AI QUERIES
    # ==========================================
    "who made you", "are you an ai", "what is your name", "tell me a joke", 
    "how does your neural network work"
]

labels = [
    # GREETINGS (6)
    "GREETING", "GREETING", "GREETING", "GREETING", "GREETING", "GREETING",
    
    # TIER 3: SEVERE (16)
    "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE",
    "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", 
    "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE", "SYMPTOM_SEVERE",
    
    # TIER 2: MODERATE (12)
    "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", 
    "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", "SYMPTOM_MODERATE", 
    "SYMPTOM_MODERATE", "SYMPTOM_MODERATE",
    
    # TIER 1: INFO (20)
    "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", 
    "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO", "INFO",
    
    # EXIT (6)
    "EXIT", "EXIT", "EXIT", "EXIT", "EXIT", "EXIT",
    
    # GENERAL (5)
    "GENERAL", "GENERAL", "GENERAL", "GENERAL", "GENERAL"
]

# Quick safety check to ensure arrays match perfectly before training!
if len(texts) != len(labels):
    print(f"⚠️ ERROR: Texts ({len(texts)}) and Labels ({len(labels)}) do not match!")

# 2. Extract Deep Semantic Features (Vectors) instead of just word counts
print("📊 Converting text to Semantic Vectors...")
X_train = embedder.encode(texts)

# 3. Build and Train the Neural Network on the Semantic Vectors
print("⚙️ Training Multi-Layer Perceptron Neural Network...")
nn_model = MLPClassifier(
    hidden_layer_sizes=(64, 32), 
    activation='relu', 
    solver='adam', 
    max_iter=1000,
    random_state=42
)

nn_model.fit(X_train, labels) 

# 4. Save ONLY the Neural Network (the embedder is downloaded dynamically)
with open("router_nn.pkl", "wb") as f:
    pickle.dump(nn_model, f)

print("✅ Training Complete! Neural Network weights saved as 'router_nn.pkl'.")