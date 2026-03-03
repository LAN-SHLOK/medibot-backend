# if you dont use pipenv uncomment the following:
# from dotenv import load_dotenv
# load_dotenv()

#VoiceBot UI with Gradio
import os
import gradio as gr

from brainLLM import encode_image, analyze_image_with_query
from voice_patient import record_audio, transcribe_with_groq
from voice_doctor import text_to_speech_with_gtts, text_to_speech_with_edge

#load_dotenv()

system_prompt="""You are Medibot. Analyze the medical image provided.
1. Reply in the SAME language the user is speaking (Hindi/English/Gujarati).
2. Identify the condition seen in the image.
3. Suggest 2-3 practical home remedies or next steps.
4. Keep the answer short (2-3 sentences) and conversational.
5. NO Markdown. NO special characters.
6. If unsure, say "I am not a doctor, please consult a healthcare professional for an accurate diagnosis.
7. and answer like a human not a robot.
8. Use empathetic and comforting language.
9. Greet the patient warmly at the start of your response.
10. End with a positive note and well wishes.
11. If the image is unclear, politely ask for a clearer image.
"""


def process_inputs(audio_filepath, image_filepath):
    speech_to_text_output = transcribe_with_groq(GROQ_API_KEY=os.environ.get("GROQ_API_KEY"), 
                                                 audio_filepath=audio_filepath,
                                                 stt_model="whisper-large-v3")

    # Handle the image input
    if image_filepath:
        doctor_response = analyze_image_with_query(query=system_prompt+speech_to_text_output, encoded_image=encode_image(image_filepath), model="meta-llama/llama-4-scout-17b-16e-instruct") #model="meta-llama/llama-4-maverick-17b-128e-instruct") 
    else:
        doctor_response = "No image provided for me to analyze"

    voice_of_doctor = text_to_speech_with_edge(input_text=doctor_response, output_filepath="final.mp3") 

    return speech_to_text_output, doctor_response, voice_of_doctor


# Create the interface
iface = gr.Interface(
    fn=process_inputs,
    inputs=[
        gr.Audio(sources=["microphone"], type="filepath"),
        gr.Image(type="filepath")
    ],
    outputs=[
        gr.Textbox(label="Speech to Text"),
        gr.Textbox(label="Doctor's Response"),
        gr.Audio("Temp.mp3")
    ],
    title="AI Doctor with Vision and Voice"
)

iface.launch(debug=True)

#http://127.0.0.1:7860