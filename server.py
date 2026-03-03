import sys
import os
import shutil
import asyncio
import json
import sqlite3
import hashlib
import uuid
import uvicorn
import base64
import edge_tts
from dotenv import load_dotenv
from fpdf import FPDF 
import threading
from langchain_groq import ChatGroq
from typing import Optional
import queue

audio_out_queue = queue.Queue()

# ==========================================
# 0. CONFIGURATION & SETUP
# ==========================================

load_dotenv(override=True)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from pydantic import BaseModel
from load_db import medical_db 



app = FastAPI(title="MediBot Brain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/scans", exist_ok=True)
os.makedirs("static/reports", exist_ok=True)
os.makedirs("temp_audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================
# 1. DATABASE & IMPORTS
# ==========================================
def init_db():
    try:
        conn = sqlite3.connect('medibot.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                username TEXT,
                password_hash TEXT,
                auth_method TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f" Database Init Error: {e}")

init_db()

try:
    from graph_agent import app as medical_graph
    from agents.desk_agent import run_router_agent 
    from agents.classification_agent import run_triage_agent
    from agents.specialist import run_specialist_agent
    from agents.judge import run_judge_agent
    from injury_scanner import analyze_image 
except ImportError as e:
    print(f" Import Error: {e}")
    sys.exit(1)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
async def generate_audio_base64(text):
    if not text: return None
    try:
        filename = f"temp_audio/speech_{uuid.uuid4()}.mp3"
        communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
        await communicate.save(filename)
        with open(filename, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        try: os.remove(filename)
        except: pass
        return b64
    except: return None

async def typewriter_stream(agent_id, text, is_final=False, audio=None, risk="LOW"):
    words = text.split(" ")
    chunk_size = 3 
    for i in range(0, len(words), chunk_size):
        current_chunk = " ".join(words[:i + chunk_size])
        payload = {"agent": agent_id, "text": current_chunk}
        if is_final and (i + chunk_size) >= len(words):
            payload = {"final": text, "audio": audio, "risk": risk}
        yield json.dumps(payload) + "\n"
        await asyncio.sleep(0.04) 

class MedicalReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'MediBot AI - Diagnostic Report', 0, 1, 'C')
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} - Confidential AI Assessment', 0, 0, 'C')

def create_pdf_report(image_path, vision_text, doctor_advice, filename):
    pdf = MedicalReportPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "1. Visual Analysis", 0, 1, 'L', 1)
    if os.path.exists(image_path): pdf.image(image_path, x=10, w=100)
    pdf.ln(5)
    pdf.cell(0, 10, "2. Findings", 0, 1, 'L', 1)
    pdf.multi_cell(0, 6, vision_text)
    pdf.ln(5)
    pdf.cell(0, 10, "3. Recommendation", 0, 1, 'L', 1)
    pdf.multi_cell(0, 6, doctor_advice)
    save_path = os.path.join("static/reports", filename)
    pdf.output(save_path)
    return save_path

# ==========================================
# 4. CHAT ENDPOINT (THE FIX)
# ==========================================
SESSIONS = {}

def get_session(user_id):
    if user_id not in SESSIONS:
        #  Added 'initial_complaint' to store the symptom during intake
        SESSIONS[user_id] = {"step": "normal", "age": None, "history": None, "initial_complaint": None}
    return SESSIONS[user_id]

class ChatRequest(BaseModel):
    user_id: str
    message: str
    vision_context: Optional[str] = ""

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    user_id = request.user_id
    msg = request.message.strip()
    vision_context = request.vision_context# This is the 'msg' in the outer scope
    session = get_session(user_id)
    
    async def event_generator():
        #  ADD THIS LINE RIGHT HERE
        nonlocal msg 
        
        try:
            # 1. HANDLE INTAKE ANSWERS (Age/History)
            # 1. HANDLE INTAKE ANSWERS (Age/History)
            if session["step"] == "intake_age":
                session["age"] = msg
                session["step"] = "intake_history"
                reply = "Got it. Any past medical history? (e.g., Diabetes, Asthma, None)"
                audio = await generate_audio_base64(reply)
                async for chunk in typewriter_stream("diag", reply, True, audio): yield chunk
                return

            if session["step"] == "intake_history":
                session["history"] = msg
                session["step"] = "normal" 
                #  RESTORE ONLY THE SHORT MESSAGE! (e.g., "tell me about the image")
                msg = session["initial_complaint"] 

            # 2. INTELLIGENT ROUTING (Only analyzes the short msg!)
            symptom_keywords = [
                "pain", "fever", "symptom", "ache", "swollen", "rash", "blood", 
                "hurt", "feel", "throat", "cough", "dizzy", "vomit", "burn", 
                "cut", "wound", "infection", "redness", "stomach", "headache",
                "white patch", "tonsil", "bump", "lump", "spot", "stiff"
            ]
            is_medical_query = any(k in msg.lower() for k in symptom_keywords)

            category = run_router_agent(msg)
            if is_medical_query: category = "SYMPTOM"

            # 3. MERGE VISION & ENFORCE DOCTOR PERSONA
            full_prompt = msg
            if vision_context and vision_context.strip():
                # 🟢 FIX: Prevent Prompt Injection with strict XML boxing
                full_prompt = f"""<vision_data>
{vision_context}
</vision_data>

Patient Question: {msg}

CRITICAL SYSTEM INSTRUCTION: You are a medical professional. The image data inside the <vision_data> tags has already been analyzed for you by the Vision Scanner. Do NOT tell the patient you cannot see the image. Speak as if you are looking at the scan and base your entire analysis ONLY on the extracted data provided in the tags."""
                
                # Force it to the medical council
                category = "SYMPTOM"

            # --- SIMPLE RESPONSES ---
            if category in ["EXIT", "GREETING", "GENERAL"]:
                from agents.specialist import llm
                reply = llm.invoke(full_prompt).content
                audio = await generate_audio_base64(reply)
                async for chunk in typewriter_stream("judge", reply, True, audio): yield chunk
                return

            if category == "INFO":
                yield json.dumps({"agent": "diag", "text": "📖 Searching medical database..."}) + "\n"
                answer = run_specialist_agent(f"Define: {full_prompt}", {}, medical_db)
                audio = await generate_audio_base64(answer[:200])
                async for chunk in typewriter_stream("judge", answer, True, audio): yield chunk
                return

            # --- MEDICAL COUNCIL (SYMPTOM FLOW) ---
            if category == "SYMPTOM":
                if not session["age"]:
                    session["initial_complaint"] = msg # 🟢 SAVE SHORT MSG ONLY!
                    session["step"] = "intake_age"
                    reply = "To give a safe diagnosis, I need your age first."
                    audio = await generate_audio_base64(reply)
                    async for chunk in typewriter_stream("diag", reply, True, audio): yield chunk
                    return
                
                if session["history"] is None:
                    session["initial_complaint"] = msg # 🟢 SAVE SHORT MSG ONLY!
                    session["step"] = "intake_history"
                    reply = "Any past medical history? (Or type 'None')"
                    audio = await generate_audio_base64(reply)
                    async for chunk in typewriter_stream("diag", reply, True, audio): yield chunk
                    return

                #  START THE DEBATE
                yield json.dumps({"agent": "diag", "text": "🔬 Initializing triage protocols..."}) + "\n"
                
                triage = run_triage_agent(full_prompt, session)
                risk = triage.get("risk_level", "LOW")

                graph_inputs = {
                    "user_query": f"Age: {session['age']} | History: {session['history']} | Query: {full_prompt}",
                    "patient_data": session, "triage_result": triage,
                    "diagnosis_draft": "", "treatment_draft": "",
                    "skeptic_critique": "", "skeptic_status": "", "revision_count": 0, "final_report": ""
                }

                # ... (rest of your graph.stream code stays exactly the same) ...

                # Always Stream Graph (Specialist -> Skeptic -> Judge)
                for output in medical_graph.stream(graph_inputs):
                    for node, state in output.items():
                        if "Diagnosis" in node:
                            text = f"Dr. Diagnosis: {state.get('diagnosis_draft','')[:200]}..."
                            async for chunk in typewriter_stream("diag", text): yield chunk
                        elif "Skeptic" in node:
                            text = f"Skeptic Review: {state.get('skeptic_critique','')[:200]}..."
                            async for chunk in typewriter_stream("skeptic", text): yield chunk
                        elif "Judge" in node:
                            final_text = state.get("final_report", "")
                            audio = await generate_audio_base64(final_text[:300])
                            async for chunk in typewriter_stream("judge", final_text, True, audio, risk): 
                                yield chunk

        except Exception as e:
            print(f"Server Error: {e}")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# ==========================================
# 5. AUTH & SCAN (UNCHANGED)
# ==========================================
class LoginRequest(BaseModel): email: str; password: str
class SignupRequest(BaseModel): email: str; password: str; username: str
class SyncRequest(BaseModel): uid: str; email: str

@app.post("/manual_signup")
async def manual_signup(data: SignupRequest):
    local_id = "local_" + str(uuid.uuid4())[:8]
    hashed_pw = hashlib.sha256(data.password.encode()).hexdigest()
    try:
        conn = sqlite3.connect('medibot.db')
        conn.execute("INSERT INTO users (user_id, email, username, password_hash) VALUES (?, ?, ?, ?)", (local_id, data.email, data.username, hashed_pw))
        conn.commit(); conn.close()
        return JSONResponse(status_code=201, content={"status": "success", "user_id": local_id})
    except sqlite3.IntegrityError: return JSONResponse(status_code=409, content={"status": "fail", "message": "Email already exists"})

@app.post("/manual_login")
async def manual_login(data: LoginRequest):
    hashed_pw = hashlib.sha256(data.password.encode()).hexdigest()
    conn = sqlite3.connect('medibot.db'); cursor = conn.cursor()
    cursor.execute("SELECT user_id, email, username FROM users WHERE email=? AND password_hash=?", (data.email, hashed_pw))
    user = cursor.fetchone(); conn.close()
    if user: return {"status": "success", "user_id": user[0], "email": user[1], "username": user[2]}
    else: return JSONResponse(status_code=401, content={"status": "fail", "message": "Invalid credentials"})

@app.post("/sync_user")
async def sync_user(data: SyncRequest):
    try:
        conn = sqlite3.connect('medibot.db')
        conn.execute("INSERT OR IGNORE INTO users (user_id, email, auth_method) VALUES (?, ?, 'firebase')", (data.uid, data.email))
        conn.commit(); conn.close()
        return {"status": "synced"}
    except Exception as e: return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================
#  SINGLE FAST AGENT FOR VOICE
# ==========================================
voice_llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"), 
    model_name="llama-3.1-8b-instant", # Ultra-fast model
    temperature=0.3
)

voice_thread = None
is_voice_running = False

def run_voice_core():
    global is_voice_running 
    print("\n --- FAST GPU VOICE ENGINE STARTED ---")
    
    try:
        from Medibot_Voice.audio_engine import get_engine
        engine = get_engine()
        engine.is_running = True 
        
        def send_to_frontend(data):
            audio_out_queue.put(data)
        engine.frontend_callback = send_to_frontend
        
        while is_voice_running:
            print("\n Listening...")
            user_audio = engine.listen()
            
            if not is_voice_running: break 
            
            # STT: Will be instant on GPU with Whisper Tiny
            transcript = engine.transcribe(user_audio)
            
            if not transcript or len(transcript) < 2:
                continue 
                
            print(f" You: {transcript}")
            
            if "stop voice" in transcript.lower() or "exit" in transcript.lower():
                print(" Voice command recognized. Shutting down.")
                break

            # --- THE SINGLE AGENT RAG LOGIC ---
            print("⚡ [Agent] Thinking...")
            context = "No specific records found."
            
            # Pull directly from your FAISS Database
            if medical_db:
                docs = medical_db.similarity_search(transcript, k=2)
                if docs:
                    context = "\n".join([doc.page_content for doc in docs])
            
            # Direct prompt to Groq (Returns in ~0.5 seconds)
            prompt = f"""You are MediBot, a helpful AI medical assistant. 
            Medical Context: {context}
            User Query: {transcript}
            
            CRITICAL INSTRUCTION: Reply in exactly 1 or 2 short sentences. Speak naturally like a human. Do not use formatting like bold or bullet points."""
            
            response_text = voice_llm.invoke(prompt).content
            print(f"🤖 AI: {response_text}")

            # TTS and Output
            was_interrupted = asyncio.run(engine.speak_with_interruption(response_text))

            if was_interrupted:
                print(" Interrupted! Listening immediately...")
                continue 

    except Exception as e:
        import traceback
        print("\n CRITICAL VOICE THREAD CRASH:")
        traceback.print_exc()
        # 🟢 FIX: Notify Frontend that the backend crashed!
        try:
            send_to_frontend({"action": "stop", "error": "Backend Voice Engine crashed: " + str(e)})
        except:
            pass
    finally:
        is_voice_running = False
        print(" FAST VOICE ENGINE STOPPED.\n")

# ==========================================
# 7. VOICE API ENDPOINTS
# ==========================================
@app.post("/api/voice/start")
async def start_voice_endpoint():
    global voice_thread, is_voice_running
    
    if is_voice_running:
        return {"status": "active", "message": "Voice is already running."}
    
    # Start the continuous loop in the background
    is_voice_running = True
    voice_thread = threading.Thread(target=run_voice_core, daemon=True)
    voice_thread.start()
    
    return {"status": "active", "message": "Voice Core Online"}

@app.post("/api/voice/stop")
async def stop_voice_endpoint():
    global is_voice_running
    is_voice_running = False # Breaks the loop
    return {"status": "inactive", "message": "Stopping Voice Core..."}

@app.get("/api/voice/stream")
async def voice_stream(request: Request):
    """Streams the audio bytes from the background Voice Engine thread back to the Browser."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = audio_out_queue.get_nowait()
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.05)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/scan")
async def scan_endpoint(file: UploadFile = File(...)):
    scan_id = str(uuid.uuid4())[:8]
    temp_path = f"static/scans/scan_{scan_id}.jpg"
    with open(temp_path, "wb") as b: shutil.copyfileobj(file.file, b)
    
    vision_text = analyze_image(temp_path)
    
    # 🟢 FIX: Route through triage to get risk level
    triage = run_triage_agent(vision_text, {"age": "Unknown", "history": "None"})
    risk_level = triage.get("risk_level", "MEDIUM")
    
    severity_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    severity_score = severity_map.get(risk_level.upper(), 2)
    
    council_result = medical_graph.invoke({
        "user_query": vision_text, "patient_data": {"age": "Unknown", "history": "None"},
        "triage_result": triage, "diagnosis_draft": "", "treatment_draft": "",
        "skeptic_critique": "", "skeptic_status": "", "revision_count": 0, "final_report": ""
    })
    final_advice = council_result.get("final_report", "Complete.")
    pdf_path = create_pdf_report(temp_path, vision_text, final_advice, f"report_{scan_id}.pdf")
    audio = await generate_audio_base64(final_advice[:200])
    
    short_verdict = vision_text[:50] + "..." if len(vision_text) > 50 else vision_text
    
    return {
        "summary": final_advice, 
        "report_url": f"http://127.0.0.1:5000/{pdf_path}", 
        "audio": audio,
        "verdict": short_verdict,
        "severity_score": severity_score
    }

@app.get("/")
async def read_root():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"status": "MediBot Chat Server Running"}

import random
from pydantic import BaseModel

# ==========================================
# 8. REINFORCEMENT LEARNING (MULTI-ARMED BANDIT)
# ==========================================
# Our "Q-Table" storing the expected value of showing each button
rl_actions = {
    "btn_causes": {"text": "What are the common causes?", "q_value": 0.0, "count": 0},
    "btn_home": {"text": "Are there home remedies?", "q_value": 0.0, "count": 0},
    "btn_danger": {"text": "When should I see a doctor?", "q_value": 0.0, "count": 0},
    "btn_meds": {"text": "What medicines help?", "q_value": 0.0, "count": 0},
    "btn_explain": {"text": "Can you explain that simpler?", "q_value": 0.0, "count": 0},
    "btn_prevention": {"text": "How can I prevent this?", "q_value": 0.0, "count": 0}
}

class RewardRequest(BaseModel):
    action_id: str

@app.get("/api/rl/suggestions")
async def get_rl_suggestions():
    """Epsilon-Greedy Action Selection with Tie-Breaking"""
    epsilon = 0.3  # Bumped to 30% exploration for testing
    
    if random.random() < epsilon:
        # EXPLORE: Pick 3 completely random actions
        print(" [RL Agent] Exploring new actions...")
        selected_keys = random.sample(list(rl_actions.keys()), 3)
    else:
        # EXPLOIT: Pick the top 3 actions with the highest Q-value
        print(" [RL Agent] Exploiting best known actions...")
        
        #  THE FIX: Add a tiny random float (0.0001) to break ties!
        sorted_actions = sorted(
            rl_actions.keys(), 
            key=lambda k: rl_actions[k]["q_value"] + random.uniform(0, 0.001), 
            reverse=True
        )
        selected_keys = sorted_actions[:3]
        
    suggestions = [{"id": k, "text": rl_actions[k]["text"]} for k in selected_keys]
    return {"suggestions": suggestions}

@app.post("/api/rl/reward")
async def update_rl_reward(req: RewardRequest):
    """Update Q-Value using the RL update rule"""
    if req.action_id in rl_actions:
        alpha = 0.1  # Learning rate
        reward = 1.0 # Positive reinforcement for a click
        
        # Q(a) = Q(a) + alpha * [Reward - Q(a)]
        current_q = rl_actions[req.action_id]["q_value"]
        rl_actions[req.action_id]["q_value"] = current_q + alpha * (reward - current_q)
        rl_actions[req.action_id]["count"] += 1
        
        print(f" [RL Agent] Reward applied to '{req.action_id}'. New Q-Value: {rl_actions[req.action_id]['q_value']:.4f}")
        return {"status": "success", "new_q": rl_actions[req.action_id]["q_value"]}
    return {"status": "ignored"}

if __name__ == "__main__":
    print(" MediBot Ultimate (Server): Chat + Auth + Voice + Camera Active on Port 5000.")
    uvicorn.run(app, host="0.0.0.0", port=5000)