import random
import json
import logging
import difflib
import PyPDF2
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Firebase app (only once)
cred_path = "terramaster-6f801-firebase-adminsdk-5cl3a-ee5a7e5fc6.json"
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize OpenAI client
client = OpenAI(
    api_key="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"
)

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

# Extract text from PDF
def extract_text_from_pdf_url(pdf_url):
    text = ""
    try:
        response = requests.get(pdf_url)
        if response.status_code == 200:
            with open("/tmp/temp.pdf", "wb") as file:  # for serverless: use /tmp directory
                file.write(response.content)
            
            with open("/tmp/temp.pdf", "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:
                        text += extracted_text + "\n"
    except Exception as e:
        logging.error(f"Error extracting text from PDF URL {pdf_url}: {e}")
    return text.strip()

# Get all PDF texts
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
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:trmh::BM9AR4FW",
            messages=[{"role": "user", "content": user_message}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}", exc_info=True)
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

# Serverless handler
def handler(request):
    if request.method != "POST":
        return {"statusCode": 405, "body": json.dumps({"text": "Method Not Allowed"})}
    
    try:
        body = request.json()
        user_message = body.get("message", "").strip()

        if not user_message:
            return {"statusCode": 400, "body": json.dumps({"text": "Error: Message cannot be empty."})}

        greeting_keywords = ["hello", "hi", "hey", "good morning", "good evening", "howdy"]
        appreciation_keywords = ["thank you", "thanks", "much appreciated", "grateful", "thankful", "cheers"]
        closing_keywords = ["goodbye", "see you later", "bye", "cyl"]
        incorrect_keywords = ["wrong", "incorrect", "mistake", "not right", "error", "that's wrong", "that's not correct"]

        if any(greet in user_message.lower() for greet in greeting_keywords):
            return {"statusCode": 200, "body": json.dumps({"text": "Hello, I'm TerraBot. How can I assist you today?"})}

        if any(appreciate in user_message.lower() for appreciate in appreciation_keywords):
            appreciation_responses = [
                "You're welcome!", "Happy to help!", "Anytime!", 
                "Glad I could assist you.", "You're most welcome!", "No problem at all!"
            ]
            return {"statusCode": 200, "body": json.dumps({"text": random.choice(appreciation_responses)})}

        if any(close in user_message.lower() for close in closing_keywords):
            closing_responses = [
                "Goodbye! Have a great day!", "See you later! Reach out if you need land help.",
                "Take care! Let me know if you have more land-related questions.",
                "Bye! I'm here whenever you need land info.", "Farewell! Happy to assist anytime"
            ]
            return {"statusCode": 200, "body": json.dumps({"text": random.choice(closing_responses)})}

        if any(incorrect in user_message.lower() for incorrect in incorrect_keywords):
            apology_responses = [
                "I apologize for the mistake. Let me correct that for you.",
                "Sorry about that! Let me try again.",
                "My apologies for the error! How can I help you further?",
                "Oops! I made a mistake. Please allow me to fix it.",
                "Sorry for the confusion! I'll do my best to correct it.",
                "I’m sorry, I didn’t get that right. Let me assist you properly."
            ]
            return {"statusCode": 200, "body": json.dumps({"text": random.choice(apology_responses)})}

        if not is_land_related(user_message):
            return {"statusCode": 403, "body": json.dumps({"text": "Sorry, this question is not related to land or property. I can only help with land-related queries."})}

        dataset = load_data()
        response = find_best_match(user_message, dataset)

        if response is None:
            response = search_pdfs(user_message)

        if response is None:
            response = get_openai_response(user_message)

        return {"statusCode": 200, "body": json.dumps({"text": response})}

    except Exception as e:
        logging.error(f"Unexpected server error: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"text": "An unexpected error occurred."})}
