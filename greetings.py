import random
import datetime
import pytz
import os
import openai
from dotenv import load_dotenv
import logging

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
openai.api_key = api_key
client = openai
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- English Greetings ---
GREETING_KEYWORDS_EN = ["hello", "hi", "hey", "good morning", "good evening", "howdy"]
GREETING_RESPONSES_EN = [
    "Hello, I'm TerraBot, your land information assistant. How can I help you with land matters today?",
    "Hi there! How can I assist you with your land-related questions?",
    "Hey! Need help with land or property matters? Just ask!",
    "Waz up! I'm here to provide information about land and property. How can I help?",
    "Wow, you're here! If you have any land-related questions, I'm your assistant!",
    "Howdy! Need assistance with land or property? I'm here to help!"
]

# --- Bisaya Greetings and Translation ---
BISAYA_GREETING_KEYWORDS = {
    "buntag": ["maayong", "mayng", "mayong"],
    "hapon": ["maayong", "mayng", "mayong"],
    "gabii": ["maayong", "mayng", "mayong"],
    "kumusta": [],
    "oi": []
}
BISAYA_GREETING_RESPONSES = {
    "buntag": [
        "Maayong buntag kanimo!",
        "Buntag! Hinaot nga maayo ang imong sinugdanan sa adlaw.",
        "Maayong buntag! Andam na ba ka sa imong mga pangutana bahin sa yuta karon?",
        "Pagkanindot sa buntag! Unsa may akong ikatabang kanimo?"
    ],
    "hapon": [
        "Maayong hapon kanimo!",
        "Hapon na! Nanghinaut ko nga maayo ang imong pagpadayon sa adlaw.",
        "Maayong hapon! Naa ka bay mga pangutana nga akong matubag karon?",
        "Maayong hapon! Unsa may imong gihunahuna bahin sa yuta karong hapona?"
    ],
    "gabii": [
        "Maayong gabii kanimo!",
        "Gabii na! Hinaot nga nakapahulay ka og maayo karong adlawa.",
        "Maayong gabii! Andam na ba ka mohunong sa imong mga buluhaton o naa pa kay pangutana?",
        "Maayong gabii! Manghinaut ko nga maayo ang imong pagkatulog unya."
    ],
    "kumusta": [
        "Kumusta man ka?",
        "Okay ra ko, salamat sa pagpangutana!",
        "Kumusta! Unsa may imong tuyo karon?",
        "Maayong adlaw/hapon/gabii! Kumusta ka?" # Could be any time of day
    ],
    "oi": [
        "Oi!",
        "Hoy! Unsa man?",
        "Oi! Naa kay ipangutana?",
        "Kumusta!" # Similar to kumusta, less time-specific
    ]
}

APPRECIATION_KEYWORDS_EN = ["thank you", "thanks", "much appreciated", "grateful", "thankful", "cheers"]
APPRECIATION_RESPONSES_EN = [
    "You're welcome!", "Happy to help!", "Anytime!", "Glad I could assist you.",
    "You're most welcome!", "No problem at all!"
]

CLOSING_KEYWORDS_EN = ["goodbye", "see you later", "bye", "cyl"]
CLOSING_RESPONSES_EN = [
    "Goodbye! Have a great day!", "See you later! Reach out if you need land help.",
    "Take care! Let me know if you have more land-related questions.",
    "Bye! I'm here whenever you need land info.", "Farewell! Happy to assist anytime."
]

def handle_greeting(user_message):
    if any(user_message.lower().startswith(greeting) for greeting in GREETING_KEYWORDS_EN):
        return random.choice(GREETING_RESPONSES_EN)
    return None

def handle_appreciation(user_message):
    if any(phrase in user_message.lower() for phrase in APPRECIATION_KEYWORDS_EN):
        return random.choice(APPRECIATION_RESPONSES_EN)
    return None

def handle_closing(user_message):
    if any(phrase in user_message.lower() for phrase in CLOSING_KEYWORDS_EN):
        return random.choice(CLOSING_RESPONSES_EN)
    return None

def handle_bisaya_greeting(user_message):
    lowered_message = user_message.lower()

    for time_of_day, prefixes in BISAYA_GREETING_KEYWORDS.items():
        for prefix in prefixes:
            full_greeting = f"{prefix} {time_of_day}"
            if lowered_message.startswith(full_greeting):
                responses = BISAYA_GREETING_RESPONSES.get(time_of_day)
                if responses:
                    return random.choice(responses)
                return "Kumusta!" # Fallback

        # Handle "kumusta" and "oi" directly
        if lowered_message.startswith(time_of_day) and not prefixes:
            responses = BISAYA_GREETING_RESPONSES.get(time_of_day)
            if responses:
                return random.choice(responses)
            return "Kumusta!" # Fallback

    return None

def get_automatic_greeting():
    cebu_timezone = pytz.timezone('Asia/Manila')
    current_hour = datetime.datetime.now(cebu_timezone).hour

    if 5 <= current_hour < 12:
        return random.choice(["Maayong buntag!", "Good morning!"]) + " How can I help you with land matters today?"
    elif 12 <= current_hour < 18:
        return random.choice(["Maayong hapon!", "Good afternoon!"]) + " How can I help you with land matters today?"
    else:
        return random.choice(["Maayong gabii!", "Good evening!"]) + " How can I help you with land matters today?"

def translate_to_bisaya(text_en):
    try:
        translation_prompt = f"Translate the following English text to Cebuano (Bisaya): '{text_en}'"
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": translation_prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI Translation Error: {e}", exc_info=True)
        return "Pasensya na, adunay problema sa paghusay."