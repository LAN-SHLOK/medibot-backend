import os
import torch
import sounddevice as sd
import numpy as np
import edge_tts
import pygame
import asyncio
import time
import base64
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

# ==========================================
# ⚡ SUPERCHARGED CONFIGURATION
# ==========================================
MODEL_ID = "openai/whisper-tiny.en" 
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
SAMPLE_RATE = 16000

# SENSITIVITY SETTINGS
SILENCE_THRESHOLD = 0.01      
SPEECH_THRESHOLD = 0.03       
MAX_RECORD_SECONDS = 10       
SILENCE_DURATION_TO_STOP = 0.8 

print(f"🚀 Initializing FAST Audio Engine on {DEVICE.upper()}...")

class VolumeRingBuffer:
    def __init__(self, capacity=5):
        self.capacity = capacity
        self.buffer = [0.0] * capacity
        self.head = 0
        self.is_full = False

    def add(self, val):
        self.buffer[self.head] = val
        self.head = (self.head + 1) % self.capacity 
        if self.head == 0: self.is_full = True

    def get_average(self):
        if not self.is_full and self.head == 0: return 0.0
        count = self.capacity if self.is_full else self.head
        return sum(self.buffer) / count

class AudioEngine:
    def __init__(self):
        self.is_speaking = False
        print(f"   [Engine] Loading Whisper Processor ({MODEL_ID})...")
        self.processor = AutoProcessor.from_pretrained(MODEL_ID)
        
        print(f"   [Engine] Loading Whisper Model on {DEVICE}...")
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            MODEL_ID, 
            torch_dtype=torch.float16 if "cuda" in DEVICE else torch.float32, 
            low_cpu_mem_usage=True
        ).to(DEVICE)
        
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"⚠️ Warning: Audio device error: {e}")
            
        self.is_running = False 
        self.frontend_callback = None

    def get_mic_volume(self):
        try:
            recording = sd.rec(int(0.1 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
            sd.wait()
            return np.linalg.norm(recording) * 10
        except:
            return 0

    def listen(self):
        print("👂 Listening (Speak now)...")
        audio_buffer = []
        silence_start = None
        speech_started = False
        start_time = time.time()
        
        smoother = VolumeRingBuffer(capacity=5) 
        
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
            while self.is_running: 
                chunk, _ = stream.read(4000) 
                if not self.is_running: break

                raw_volume = np.linalg.norm(chunk) * 10
                smoother.add(raw_volume)
                avg_volume = smoother.get_average()
                
                audio_buffer.append(chunk)

                if avg_volume > SPEECH_THRESHOLD:
                    if not speech_started:
                        print("   (Speech Detected...)")
                        speech_started = True
                    silence_start = None 
                
                elif speech_started and avg_volume < SILENCE_THRESHOLD:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_DURATION_TO_STOP:
                        print("   (Silence detected, processing...)")
                        break 
                
                if time.time() - start_time > MAX_RECORD_SECONDS:
                    break

        if not self.is_running: return np.array([])
        if not audio_buffer: return np.array([])
        return np.concatenate(audio_buffer, axis=0).flatten()

    def transcribe(self, audio_data):
        if len(audio_data) < SAMPLE_RATE: return "" 
        print("⚡ Transcribing...")
        
        # 🟢 This is the line that was crashing! 
        inputs = self.processor(audio_data, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        input_features = inputs.input_features.to(DEVICE, dtype=torch.float16 if "cuda" in DEVICE else torch.float32)

        with torch.no_grad():
            generated_ids = self.model.generate(input_features)
        
        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        
        forbidden = ["Thank you.", "MBC", "You", "Watching", "Subtitles"]
        if any(f in text for f in forbidden) or len(text) < 2: return ""
            
        return text

    async def speak_with_interruption(self, text):
        if not text or not self.is_running: return False
        self.is_speaking = False
        print(f"🗣️ AI: {text}")
        
        output_file = f"response_{int(time.time())}.mp3"
        try:
            communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
            await communicate.save(output_file)

            if self.frontend_callback:
                with open(output_file, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                self.frontend_callback({"action": "play", "audio": b64})
                
                interrupted = False
                print("   (Monitoring for interruption via Frontend...)")
                
                INTERRUPTION_LIMIT = 0.5
                approx_duration = len(text.split()) * 0.45 + 1.0 
                
                start_time = time.time()
                while time.time() - start_time < approx_duration and self.is_running:
                    vol = self.get_mic_volume()
                    
                    if vol > INTERRUPTION_LIMIT:
                        print(f"🛑 INTERRUPTED! (Vol: {vol:.2f})")
                        self.frontend_callback({"action": "stop"})
                        interrupted = True
                        break 
                    
                    await asyncio.sleep(0.05)
            else:
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                
                interrupted = False
                print("   (Monitoring for interruption...)")
                
                INTERRUPTION_LIMIT = 0.5

                while pygame.mixer.music.get_busy() and self.is_running:
                    vol = self.get_mic_volume()
                    
                    if vol > INTERRUPTION_LIMIT:
                        print(f"🛑 INTERRUPTED! (Vol: {vol:.2f})")
                        pygame.mixer.music.stop()
                        interrupted = True
                        break 
                    
                    await asyncio.sleep(0.05)
                
                pygame.mixer.music.unload()

            self.is_speaking = False
            if os.path.exists(output_file): os.remove(output_file)
                
            return interrupted
        except Exception as e:
            print(f"TTS Error: {e}")
            return False

def get_engine():
    return AudioEngine()