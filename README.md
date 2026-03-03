# 🎙️ Medibot V2 - Intelligence & Voice Backend
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.103.1-009688)
![Groq](https://img.shields.io/badge/LLM-Groq-orange)
![License](https://img.shields.io/badge/License-MIT-green)
The **Intelligence & Voice Backend** serves as the cognitive core of Medibot V2. It orchestrates complex multi-agent medical triage, processes real-time contextual chat, and features a near-zero latency Server-Sent Events (SSE) Voice Engine for dynamic speech synthesis.
---
## ✨ Core Features
### 1. Multi-Agent Medical Council
Input is not handled by a single LLM. Instead, symptoms are routed through an advanced Agentic Graph:
- **Triage Agent:** Conducts initial symptom assessment and severity mapping.
- **Specialist Agent:** Deep-dives into specific medical domains based on the Triage output.
- **Chief Medical Judge:** Reviews the preceding assessments to formulate a final, medically sound verdict and Risk Score.
### 2. High-Fidelity Voice Engine
- **Local STT (Speech-to-Text):** Utilizes `Whisper-Tiny` operating on `float16` precision to bypass CPU bottlenecks and run directly on CUDA GPU architecture.
- **Streaming TTS (Text-to-Speech):** Employs `edge_tts` coupled with an SSE (`EventSource`) pipeline. Audio bytecode is chunked and streamed as base64 encodings to the frontend, enabling the avatar to speak instantaneously without waiting for full generation.
### 3. Fortified Security & Prompt Injection Shielding
Aggressively sanitizes inputs originating from the Vision Scanner pipeline. Extracted OCR/Vision text is strictly demarcated within `<vision_data>` XML tags, neutralizing adversarial injection attempts designed to alter the LLM's system persona.
### 4. Resilient Daemon Threading
The Voice Engine thread is wrapped in comprehensive error-recovery mechanisms. In the event of an upstream LLM timeout or unhandled exception, the thread gracefully broadcasts a terminal `{"action": "stop"}` payload via SSE, allowing the UI client to recover seamlessly.
---
## 🛠 Prerequisites
- **Python:** Version 3.10 or higher.
- **API Keys:** A valid Groq API Key (`GROQ_API_KEY`) is mandatory for LLM inference.
- **FFmpeg:** Required for audio processing (must be added to system PATH).
## 🚀 Installation & Setup
1. **Navigate to the Directory:**
   ```bash
   cd Chat
   ```
2. **Create a Virtual Environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure dependencies like `fastapi`, `uvicorn`, `edge-tts`, `transformers`, `torch`, `whisper`, and `langchain-groq` are present).*
4. **Configure Environment Variables:**
   Create a `.env` file in the root of the `Chat` directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```
5. **Start the Server:**
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```
---
## 📡 API Reference
### `POST /chat`
Processes standard text-based medical queries through the LLM Council.
- **Payload:** `{"message": "I am experiencing severe chest pain...", "context": "..."}`
- **Response:** JSON encapsulating the council's thought process, final verdict, Risk level, and reinforcement-learning suggested follow-ups.
### `GET /voice/stream`
Establishes a continuous Server-Sent Events (SSE) connection.
- **Behavior:** Accepts audio blob uploads, infers text via Whisper, processes through the LLM, and streams back synchronous JSON containing `text_chunk` alongside base64 encoded MP3 audio fragments.
---
*Designed with precision for Medibot V2.*
