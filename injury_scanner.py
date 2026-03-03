import cv2
import numpy as np
import base64
import os
from groq import Groq
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.environ.get("GROQ_API_KEY") 
MODEL_ID = "meta-llama/llama-4-scout-17b-16e-instruct"

client = Groq(api_key=API_KEY)

def highlight_injury(image):
    """
    Uses Color Segmentation and Contour Detection to outline the injury.
    """
    # 1. Convert to HSV (Hue, Saturation, Value) color space
    # Skin injuries (cuts, rashes, burns) are usually RED/PINK.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 2. Define Range for "Red/Pink" colors (Injury colors)
    # Lower Red Mask (0-10)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    # Upper Red Mask (170-180)
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])

    # Combine masks to catch all red shades
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 + mask2

    # 3. Clean up noise (remove small dots)
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 4. Find Contours (Outlines)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 5. Draw the largest contour (The Injury)
    if contours:
        # Find the biggest red area
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Filter: Only draw if it's big enough (ignore mosquito bites/noise)
        if cv2.contourArea(largest_contour) > 500:
            # Draw a thick Cyan outline around it
            cv2.drawContours(image, [largest_contour], -1, (255, 255, 0), 3)
            
            # Draw a bounding box with text
            x, y, w, h = cv2.boundingRect(largest_contour)
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(image, "TARGET LOCK", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return image

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path):
    try:
        if not API_KEY:
            return "Error: GROQ_API_KEY not found."

        print(f" Mapping Injury: {image_path}")
        
        # --- OPENCV PROCESSING START ---
        img = cv2.imread(image_path)
        if img is None:
            return "Error: OpenCV could not read the image."
            
        # 1. Map the Injury (Draw the Outline)
        mapped_img = highlight_injury(img.copy())
        
        # 2. Save the "Scanned" version (Optional: You can serve this back to UI later)
        # We overwrite the original temp file with the mapped version so the AI sees what we outlined!
        # (Or you can choose to send the clean one. Sending the mapped one helps AI see what YOU see).
        cv2.imwrite(image_path, mapped_img) 
        
        print(" Injury Mapped & Saved.")
        # --- OPENCV PROCESSING END ---

        # Now send the MAPPED image to the AI
        base64_image = encode_image(image_path)
        
        prompt = """
        You are an expert Trauma Surgeon.
        I have highlighted the potential injury area in GREEN/CYAN.
        1. Look at the outlined area.
        2. IDENTIFY the condition (Cut, Burn, Infection, Rash).
        3. DIAGNOSE severity.
        4. ADVISE immediate steps.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model=MODEL_ID,
            temperature=0.1,
            max_tokens=300
        )

        diagnosis = chat_completion.choices[0].message.content
        return diagnosis

    except Exception as e:
        return f"Error analyzing image: {str(e)}"