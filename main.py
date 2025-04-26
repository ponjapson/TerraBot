import random
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import difflib
import PyPDF2
import requests
import os
import firebase_admin
from firebase_admin import credentials, firestore
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)
# Hardcoded Firebase Admin credentials
firebase_cred_json = os.environ.get("FIREBASE_CRED_JSON")
if firebase_cred_json:
    cred = credentials.Certificate(json.loads(firebase_cred_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    raise Exception("Firebase credentials not found.")

# Load dataset function
def load_data():
    try:
        with open("datasets/trmhdataset.jsonl", "r", encoding="utf-8") as file:
            return [json.loads(line) for line in file]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading dataset: {e}")
        return []

# Find best dataset match
def find_best_match(user_input, dataset):
    user_messages = [conv["messages"][-2]["content"] for conv in dataset if len(conv["messages"]) >= 2]
    closest_match = difflib.get_close_matches(user_input, user_messages, n=1, cutoff=0.7)
    
    if closest_match:
        for conv in dataset:
            if conv["messages"][-2]["content"] == closest_match[0]:
                return conv["messages"][-1]["content"]
    return None

# Extract text from a PDF URL
def extract_text_from_pdf_url(pdf_url):
    text = ""
    try:
        response = requests.get(pdf_url)
        if response.status_code == 200:
            with open("temp.pdf", "wb") as file:
                file.write(response.content)
            
            with open("temp.pdf", "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:
                        text += extracted_text + "\n"
    except Exception as e:
        logging.error(f"Error extracting text from PDF URL {pdf_url}: {e}")
    return text.strip()

# Get all PDF texts from Firebase Firestore
def fetch_pdfs_from_firebase():
    pdf_texts = []
    try:
        pdf_docs = db.collection("pdfs").stream()
        for doc in pdf_docs:
            pdf_url = doc.to_dict().get("url")
            if pdf_url:
                text = extract_text_from_pdf_url(pdf_url)
                if text:
                    pdf_texts.append({"filename": doc.id, "content": text})
    except Exception as e:
        logging.error(f"Error fetching PDFs from Firebase: {e}")
    return pdf_texts

# Search PDFs for relevant text
def search_pdfs(user_question):
    pdf_data = fetch_pdfs_from_firebase()
    for pdf in pdf_data:
        matches = difflib.get_close_matches(user_question, pdf["content"].split("\n"), n=1, cutoff=0.6)
        if matches:
            return matches[0][:500]
    return None

# Fetch response from OpenAI
def get_openai_response(user_message):
    try:
        # Get the response from OpenAI
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:trmh::BM9AR4FW",
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Access the content of the response and return it
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}", exc_info=True)  # Logs the error with traceback
        return "Sorry, I'm experiencing issues connecting to OpenAI."

# LAND KEYWORDS
LAND_KEYWORDS = [
    "land","surveyor","processor", "survey","teritory", "boundary", "ownership", "property", "real estate", "acessor", 
    "deed of sale", "Title Deed", "zoning", "processing", "parcel", "lot", "terrain", "geodetic", "land title transfer", 
    "topography", "coordinates", "GIS", "easement", "tenure", "leasehold", "freehold",  
    "subdivision", "appraisal", "mortgage", "escrow", "cadastral", "geospatial", "dispute", 
    "land use", "notary", "affidavit", "forestry", "conservation",  
    "survey marker", "land grant", "land registry", "demarcation", "surveying instruments",  
    "mapping", "cartography", "site development", "land reclamation", "environmental impact",  
    "hydrography", "title insurance", "heritage land",  
    "right of way", "geological survey", "land tenure system", "land valuation",  
    "site planning", "land tenure security", "property assessment", "legal description",  
    "land act", "urban planning", "rural land", "municipal planning", "land ownership transfer",  
    "taxation of land", "land development", "land acquisition", "land leasing", "survey regulations",
    "electronic certificate authorizing registration", "deed of donation", "deed of adjudication", "real property tax ",
    "capital gains tax", "documentary stamp tax", "transfer tax", "estate tax", "special assessment tax", "zonal valuation"
]

def is_land_related(message):
    message_lower = message.lower()
    return any(word in message_lower for word in LAND_KEYWORDS)

# Chat route
@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_data = request.get_json()
        user_message = user_data.get("message", "").strip()

        if not user_message:
            return jsonify({"text": "Error: Message cannot be empty."}), 400
        
        greeting_keywords = ["hello", "hi", "hey", "good morning", "good evening", "howdy"]
        if any(greeting in user_message.lower() for greeting in greeting_keywords):
            return jsonify({"text": "Hello, I'm TerraBot. How can I assist you today?"})
        
        appreciation_keywords = ["thank you", "thanks", "much appreciated", "grateful", "thankful", "cheers"]
        appreciation_responses = [
                                 "You're welcome!",
                                 "Happy to help!",
                                 "Anytime!",
                                 "Glad I could assist you.",
                                 "You're most welcome!",
                                 "No problem at all!"
                                 ]
        
        if any(phrase in user_message.lower() for phrase in appreciation_keywords):
            return jsonify({"text": random.choice(appreciation_responses)})

        closing_keywords = ["goodbye", "see you later", "bye", "cyl"]
        if any(phrase in user_message.lower() for phrase in closing_keywords):
            closing_responses = [
                                 "Goodbye! Have a great day!",
                                 "See you later! Reach out if you need land help.",
                                 "Take care! Let me know if you have more land-related questions.",
                                 "Bye! I'm here whenever you need land info.",
                                 "You're most welcome!",
                                 "Farewell! Happy to assist anytime"
                                 ]
            
            return jsonify({"text": random.choice(closing_responses)})
        
        incorrect_keywords = ["wrong", "incorrect", "mistake", "not right", "error", "that's wrong", "that's not correct"]
        if any(incorrect in user_message.lower() for incorrect in incorrect_keywords):
             apology_responses = [
                                "I apologize for the mistake. Let me correct that for you.",
                                "Sorry about that! Let me try again.",
                                "My apologies for the error! How can I help you further?",
                                "Oops! I made a mistake. Please allow me to fix it.",
                                "Sorry for the confusion! I'll do my best to correct it.",
                                "I’m sorry, I didn’t get that right. Let me assist you properly."
]
             return jsonify({"text": random.choice(apology_responses)})

        # First, check if the message is related to land
        if not is_land_related(user_message):
            return jsonify({"text": "Sorry, this question is not related to land or property. I can only help with land-related queries."}), 403

        # If land-related, check Dataset First
        dataset = load_data()
        response = find_best_match(user_message, dataset)

        # If No Dataset Answer, Search PDFs
        if response is None:
            response = search_pdfs(user_message)

        # If No PDF Match, Use OpenAI
        if response is None:
            response = get_openai_response(user_message)

        return jsonify({"text": response})

    except Exception as e:
        logging.error(f"Unexpected server error: {str(e)}")
        return jsonify({"text": "An unexpected error occurred."}), 500
    
handler = app

if __name__ == "__main__":
    app.run(debug=True)