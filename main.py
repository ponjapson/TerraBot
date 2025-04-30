import os
import logging
import requests
import difflib
import io
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
import openai
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from firebase_admin import credentials, firestore, initialize_app, _apps
from land_keywords import is_land_related_english, is_land_related_bisaya
from greetings import handle_greeting, handle_bisaya_greeting, handle_appreciation, handle_closing

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIREBASE_CRED_PATH = os.getenv('FIREBASE_CRED_JSON')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize OpenAI client
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
openai.api_key = OPENAI_API_KEY
client = openai
logging.info("OpenAI client initialized.")

# Initialize Firebase Admin
if not FIREBASE_CRED_PATH:
    raise ValueError("FIREBASE_CRED_JSON environment variable not set.")
if not os.path.exists(FIREBASE_CRED_PATH):
    raise FileNotFoundError(f"Firebase credential file not found at path: {FIREBASE_CRED_PATH}")
if not _apps:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    initialize_app(cred)
    logging.info("Firebase Initialized Successfully.")
db = firestore.client()

# --- Helper Functions ---
def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return None

def translate_text(text, target_lang='en'):
    translator = GoogleTranslator(source='auto', target=target_lang)
    try:
        return translator.translate(text)
    except Exception as e:
        logging.error(f"Error during translation: {e}")
        return text

def extract_text_from_pdf_url(pdf_url):
    text = ""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        with io.BytesIO(response.content) as pdf_buffer:
            reader = PyPDF2.PdfReader(pdf_buffer)
            for page in reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text + "\n"
        logging.info(f"Successfully extracted text from {pdf_url}")
        return text.strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading PDF from URL {pdf_url}: {e}")
    except PyPDF2.errors.PdfReadError as e:
        logging.error(f"Error reading PDF from {pdf_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error extracting text from {pdf_url}: {e}", exc_info=True)
    return ""

def fetch_knowledge_guides():
    guides = []
    logging.info("Fetching knowledge guides from Firebase...")
    try:
        for doc in db.collection("knowledge_guide").stream():
            guide_data = doc.to_dict()
            if any(guide_data.get(key) for key in ["content", "pdfUrl", "title", "extractedText", "steps"]):
                guides.append({"id": doc.id, **guide_data})
        logging.info(f"Fetched {len(guides)} knowledge guides.")
    except Exception as e:
        logging.error(f"Error fetching guides: {e}", exc_info=True)
    return guides

def find_best_match(query, candidates, cutoff=0.6):
    matches = difflib.get_close_matches(query.lower(), [str(c).lower() for c in candidates if c], n=1, cutoff=cutoff)
    return matches[0] if matches else None

def search_knowledge_guides(user_question, language=None):
    guides = fetch_knowledge_guides()
    if not guides:
        logging.warning("No knowledge guides available.")
        return None

    best_match = None
    best_score = 0
    best_guide_id = None

    for guide in guides:
        content_to_search = []
        if guide.get("title"):
            content_to_search.append(guide["title"])
        if guide.get("extractedText"):
            content_to_search.extend(guide["extractedText"].splitlines())
        if guide.get("steps") and guide.get("type") == "stepbystep":
            for step in guide["steps"]:
                if step.get("description"):
                    content_to_search.append(step["description"])

        for text in content_to_search:
            if text:
                similarity = difflib.SequenceMatcher(None, user_question.lower(), text.lower()).ratio()
                if similarity > best_score:
                    best_score = similarity
                    best_match = text
                    best_guide_id = guide.get("id")

    if best_match and best_score > 0.7:
        logging.info(f"Found relevant content in guide ID {best_guide_id} with score: {best_score}")
        summary = '. '.join(best_match.split('.')[:2]).strip()[:1000]
        return {"text": summary, "id": best_guide_id}

    logging.info("No sufficiently relevant content found in knowledge guides.")
    return None

def get_openai_response(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}")
        return "Sorry, I encountered an error."

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_data = request.get_json()
        if not user_data or "message" not in user_data:
            return jsonify({"text": "Error: Invalid request. 'message' is required."}), 400

        user_message = user_data["message"].strip()
        if not user_message:
            return jsonify({"text": "Error: No message provided."}), 400

        logging.info(f"Received message: {user_message}")
        user_language = detect_language(user_message)
        logging.info(f"Detected language: {user_language}")

        # Check for land-related content
        is_land_bisaya_keyword = is_land_related_bisaya(user_message)
        is_land_english_keyword = is_land_related_english(user_message)

        if is_land_bisaya_keyword:
            user_language = 'ceb'
            logging.info("Heuristic: Bisaya land-related keyword found, assuming Bisaya.")
        elif is_land_english_keyword:
            user_language = 'en'
            logging.info("Heuristic: English land-related keyword found, assuming English.")

        is_land_related = is_land_bisaya_keyword or is_land_english_keyword

        # If land-related
        if is_land_related:
            logging.info("Land-related message. Searching knowledge guides...")
            knowledge_response = search_knowledge_guides(user_message, language=user_language)
            if knowledge_response:
                return jsonify(knowledge_response)
            else:
                logging.info("No relevant guide found. Using OpenAI.")
                openai_response = get_openai_response(user_message)
                if user_language == 'ceb':
                    openai_response = translate_text(openai_response, target_lang='ceb')
                return jsonify({"text": openai_response})
        
        # Handle greetings, appreciation, closing
        response = handle_greeting(user_message) or \
                   handle_bisaya_greeting(user_message) or \
                   handle_appreciation(user_message) or \
                   handle_closing(user_message)
        if response:
            return jsonify({"text": response})

        # Not land-related and not a basic interaction
        logging.info("Non-land-related and not a greeting. Ignoring.")
        fallback_text = "I'm here to help with land-related concerns only."
        if user_language == 'ceb':
            fallback_text = "Nia ra ko para mutabang sa mga pangutana bahin sa yuta."
        return jsonify({"text": fallback_text})

    except Exception as e:
        logging.error(f"Error processing chat request: {e}")
        return jsonify({"text": "Sorry, an error occurred."}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
