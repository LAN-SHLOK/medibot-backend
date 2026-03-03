import asyncio
from audio_engine import get_engine
from brain import get_brain

def main():
    engine = get_engine()
    brain = get_brain()
    
    print("\n👨‍⚕️ MediBot Ready (With Emotions & Interruption).")

    # Start the conversation
    first_run = True
    
    while True:
        if first_run:
            print("\nPress [Enter] to start...")
            input()
            first_run = False
        else:
            print("\n(Listening for your reply...)")

        # 1. Listen
        user_audio = engine.listen()
        transcript = engine.transcribe(user_audio)
        print(f"📝 You said: {transcript}")

        if "exit" in transcript.lower(): break
        if len(transcript) < 2: continue

        # 2. Think (RAG)
        response = brain.get_doctor_response(transcript)

        # 3. Speak (with Interruption Check)
        was_interrupted = asyncio.run(engine.speak_with_interruption(response))

        if was_interrupted:
            print("👀 Interruption detected! Listening to your new input...")
            # 🟢 CRITICAL: This 'continue' forces the loop to restart immediately.
            # It skips waiting for silence and immediately starts recording your new question.
            # This effectively "overwrites" the AI's previous train of thought.
            continue 

if __name__ == "__main__":
    main()