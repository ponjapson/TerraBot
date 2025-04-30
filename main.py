import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
import os
import logging
import requests
import difflib
from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
import io
from dotenv import load_dotenv
import openai
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
import nltk.data
from land_keywords import is_land_related_english, is_land_related_bisaya

def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return None

def translate_google(text, target_lang='ceb'):
    translator = GoogleTranslator(source='auto', target=target_lang)
    try:
        translated = translator.translate(text)
        return translated
    except Exception as e:
        logging.error(f"Error during translation using deep_translator for text '{text[:50]}...': {e}")
        return text  # Return original text on error - CORRECTED

def split_to_sentences(text):
    try:
        tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
        return tokenizer.tokenize(text)
    except LookupError:
        nltk.download('punkt')
        tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
        return tokenizer.tokenize(text)
    except Exception as e:
        logging.error(f"Error loading sentence tokenizer: {e}")
        # Fallback to simple split if nltk fails
        return text.split('.')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
openai.api_key = api_key
client = openai
logging.info("OpenAI client initialized.")

# Initialize Firebase Admin
firebase_cred_path = os.getenv('FIREBASE_CRED_JSON')
if not firebase_cred_path:
    raise ValueError("FIREBASE_CRED_JSON environment variable not set.")
if not os.path.exists(firebase_cred_path):
    raise FileNotFoundError(f"Firebase credential file not found at path: {firebase_cred_path}")
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_cred_path)
    initialize_app(cred)
    logging.info("Firebase Initialized Successfully.")
db = firestore.client()

# --- PDF Extraction Functions ---
def extract_text_from_pdf_url(pdf_url):
    text = ""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        pdf_buffer = io.BytesIO(response.content)
        reader = PyPDF2.PdfReader(pdf_buffer)
        for page in reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                text += extracted_text + "\n"

        logging.info(f"Successfully extracted text from {pdf_url}")
        return text.strip()

    except requests.exceptions.Timeout:
        logging.error(f"Timeout error downloading PDF from URL {pdf_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading PDF from URL {pdf_url}: {e}")
    except PyPDF2.errors.PdfReadError as e:
        logging.error(f"Error reading PDF content from {pdf_url}. It might be corrupted or password-protected: {e}")
    except Exception as e:
        logging.error(f"Unexpected error extracting text from PDF URL {pdf_url}: {e}", exc_info=True)

    return ""


def fetch_knowledge_guides():
    guides = []
    logging.info("Fetching knowledge guides from Firebase 'knowledge_guide' collection...")
    try:
        guide_docs = db.collection("knowledge_guide").stream()
        count = 0
        for doc in guide_docs:
            count += 1
            guide_data = doc.to_dict()
            guide_id = doc.id
            content = guide_data.get("content")
            pdf_url = guide_data.get("pdfUrl")
            title = guide_data.get("title")  # Fetch the title
            guide_type = guide_data.get("guideType")
            extracted_text = guide_data.get("extractedText") # Fetch pre-extracted text if available
            steps = guide_data.get("steps") # Fetch steps if available
            language = guide_data.get("language") # Fetch language if available
            translated_text = guide_data.get("translatedText") # Fetch translated text if available

            logging.info(f"Fetched document ID: {guide_id}, Type: {guide_type}, Language: {language}, Translated: {translated_text is not None}") # Log translation status

            if content or pdf_url or title or extracted_text or steps:
                guides.append({
                    "id": guide_id,
                    "content": content,
                    "pdfUrl": pdf_url,
                    "title": title,
                    "type": guide_type,
                    "extractedText": extracted_text,
                    "steps": steps,
                    "language": language,
                    "translatedText": translated_text
                })

        logging.info(f"Finished processing {count} knowledge guides from 'knowledge_guide'.")
    except Exception as e:
        logging.error(f"Error fetching/processing guides from 'knowledge_guide': {e}", exc_info=True)
    return guides


def search_knowledge_guides(user_question, language=None):
    guides = fetch_knowledge_guides()
    if not guides:
        logging.warning("No knowledge guides available to search.")
        return None

    best_match_title_score = 0.8
    relevant_guide_by_title = None

    for guide in guides:
        title = guide.get("title")
        if title and difflib.SequenceMatcher(None, user_question.lower(), title.lower()).ratio() > best_match_title_score:
            logging.info(f"Found title match in Guide: {guide['id']} - Title: {title}")
            relevant_guide_by_title = guide
            break

    if relevant_guide_by_title:
        guide_type = relevant_guide_by_title.get("type", "").lower()
        steps = relevant_guide_by_title.get("steps", [])
        extracted_text = relevant_guide_by_title.get("extractedText", "")
        guide_language = relevant_guide_by_title.get("language")
        translated_text = relevant_guide_by_title.get("translatedText")

        if language == 'ceb' and translated_text:
            summary = '. '.join(translated_text.split('.')[:2]).strip()
            return {"text": summary, "id": relevant_guide_by_title.get("id")}
        elif guide_type == "stepbystep" and steps and steps[0].get("description"):
            summary = '. '.join(steps[0]["description"].split('.')[:2]).strip()
            return {"text": summary, "id": relevant_guide_by_title.get("id")}
        elif guide_type == "pdf" and extracted_text:
            summary = '. '.join(extracted_text.split('.')[:2]).strip()[:1000]
            return {"text": summary, "id": relevant_guide_by_title.get("id")}
        elif relevant_guide_by_title.get("title"):
            return {"text": relevant_guide_by_title["title"], "id": relevant_guide_by_title.get("id")}
        else:
            logging.warning(f"Title match found, but no relevant text content.")
            return None

    best_match_content = None
    best_match_score = 0.7
    best_match_guide = None

    for guide in guides:
        extracted_text = guide.get("extractedText")
        if extracted_text:
            lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
            matches = difflib.get_close_matches(user_question, lines, n=1, cutoff=best_match_score)
            if matches:
                logging.info(f"Found content match in Guide: {guide['id']} - {matches[0][:200]}...")
                best_match_guide = guide
                best_match_content = matches[0]
                break

    if best_match_content and best_match_guide:
        guide_language = best_match_guide.get("language")
        translated_text = best_match_guide.get("translatedText")
        if language == 'ceb' and translated_text:
            summary = '. '.join(translated_text.split('.')[:2]).strip()[:1000]
            return {"text": summary, "id": best_match_guide.get("id")}
        else:
            summary = '. '.join(best_match_content.split('.')[:2]).strip()[:1000]
            return {"text": summary, "id": best_match_guide.get("id")}

    logging.info(f"No sufficiently close match found in knowledge guides (title or content).")
    return None

# --- OpenAI Response ---
def get_openai_response(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}", exc_info=True)
        return "Sorry, I encountered an error while processing your request."

@app.route("/admin/translate_guide/<guide_id>", methods=["POST"])
def translate_guide(guide_id):
    try:
        guide_ref = db.collection("knowledge_guide").document(guide_id)
        guide_doc = guide_ref.get()
        if guide_doc.exists:
            guide_data = guide_doc.to_dict()
            extracted_text = guide_data.get("extractedText")
            language = guide_data.get("language")

            if language == 'en' and extracted_text:
                logging.info(f"Translating extractedText for guide ID: {guide_id}")

                sentences = split_to_sentences(extracted_text)
                translated_sentences = []
                for sentence in sentences:
                    cleaned_sentence = sentence.strip()
                    if len(cleaned_sentence) > 0:
                        try:
                            translated_sentence = translate_google(cleaned_sentence, target_lang='ceb')
                            translated_sentences.append(translated_sentence)
                        except Exception as e:
                            logging.error(f"Error translating sentence '{cleaned_sentence}': {e}")
                            translated_sentences.append(cleaned_sentence) # Keep original if translation fails

                translated_text = ". ".join(translated_sentences).strip()
                guide_ref.update({"translatedText": translated_text}) # Dinhi gi-update ang Firebase
                return jsonify({"message": f"Translation initiated for guide ID: {guide_id}"}), 200
            else:
                return jsonify({"message": f"No English extractedText found for guide ID: {guide_id}, or already translated."}), 200
        else:
            return jsonify({"error": f"Guide with ID {guide_id} not found."}), 404
    except Exception as e:
        logging.error(f"Error translating guide {guide_id}: {e}")
        return jsonify({"error": f"Error translating guide {guide_id}: {str(e)}"}), 500

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_data = request.get_json()
        if not user_data or "message" not in user_data:
            logging.warning("Received invalid request data.")
            return jsonify({"text": "Error: Invalid request data. 'message' field is required."}), 400

        user_message = user_data.get("message", "").strip()

        if not user_message:
            return jsonify({"text": "Error: No message provided."}), 400

        logging.info(f"Received message: {user_message}")

        user_language = detect_language(user_message)
        logging.info(f"Detected user language: {user_language}")

        is_land_bisaya = is_land_related_bisaya(user_message)
        is_land_english = is_land_related_english(user_message)

        is_land_related = is_land_bisaya or is_land_english

        if not is_land_related:
            logging.info("User message does not contain land-related keywords.")
            return jsonify({"text": "Sorry, I can only answer questions related to land and property."}), 200  # Or a more specific non-land response

        if is_land_bisaya:
            user_language = 'ceb'
            logging.info("Heuristic: Bisaya land-related keyword found, assuming Bisaya.")
        elif is_land_english:
            user_language = 'en'
            logging.info("Heuristic: English land-related keyword found, assuming English.")

        logging.info("User message contains land-related keywords. Searching knowledge guides...")

        knowledge_guide_response = search_knowledge_guides(user_message, language=user_language)

        if knowledge_guide_response and isinstance(knowledge_guide_response, dict):
            guide_id = knowledge_guide_response.get("id")
            guide_ref = db.collection("knowledge_guide").document(guide_id)
            guide_doc = guide_ref.get()

            if guide_doc.exists:
                guide_data = guide_doc.to_dict()
                extracted_text = guide_data.get("extractedText")
                if extracted_text and not guide_data.get("translatedText"):
                    translated_text = translate_google(extracted_text, target_lang='ceb')
                    guide_ref.update({"translatedText": translated_text})
                    logging.info(f"Guide {guide_id} translated and updated with new text.")
                    return jsonify({"text": translated_text})

            return jsonify({"text": knowledge_guide_response.get("text")})

        elif knowledge_guide_response:
            return jsonify({"text": knowledge_guide_response})
        else:
            logging.info("No relevant content found in knowledge guides. Getting OpenAI response.")
            openai_response = get_openai_response(user_message)
            if user_language == 'ceb':
                translated_response = translate_google(openai_response, target_lang='ceb')
                return jsonify({"text": translated_response})
            else:
                return jsonify({"text": openai_response})

    except Exception as e:
        logging.error(f"Error processing chat request: {e}", exc_info=True)
        return jsonify({"text": "Sorry, an error occurred while processing your request."}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)