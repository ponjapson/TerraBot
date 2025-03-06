from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import difflib
import os
import logging
import random
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# Load OpenAI API Key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

client = OpenAI(api_key=api_key)

# Path to dataset
DATA_FILE = "datasets/trmhdataset.jsonl"

# Load dataset function
def load_data():
    conversations = []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            conversations = [json.loads(line) for line in file]
        logging.info(f"Loaded {len(conversations)} conversations.")
    except FileNotFoundError:
        logging.error("Dataset file not found.")
    except json.JSONDecodeError:
        logging.error("Error decoding JSON in dataset.")
    return conversations

# Find best match from dataset
def find_best_match(user_input, dataset):
    try:
        user_messages = [
            conv["messages"][-2]["content"] for conv in dataset if len(conv["messages"]) >= 2
        ]
        closest_match = difflib.get_close_matches(user_input, user_messages, n=1, cutoff=0.7)

        if closest_match:
            for conv in dataset:
                if conv["messages"][-2]["content"] == closest_match[0]:
                    return conv["messages"][-1]["content"]
    except KeyError:
        logging.error("Error processing dataset. Check JSON structure.")
    return None  # No close match found

# List of keywords related to land topics
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

def is_land_related(question):
    """Check if the user's question is related to land topics."""
    return any(keyword in question.lower() for keyword in LAND_KEYWORDS)

# Fetch response from OpenAI
def get_openai_response(user_message):
    try:
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:trmh::B71YEiAQ",
            messages=[{"role": "user", "content": user_message}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API Error: {str(e)}")
        return "Sorry, I'm experiencing issues connecting to OpenAI."

# Chat route
@app.route("/chat", methods=["POST"])
def chat():
    user_data = request.get_json()
    user_message = user_data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    dataset = load_data()
    response = find_best_match(user_message, dataset)

    if response is None:  # If no relevant response is found
        if is_land_related(user_message):
            response = get_openai_response(user_message)  # Get AI-generated response for land topics
        else:
            response_options = [
                "I specialize in land-related topics such as surveying, zoning, and property ownership.",
                "Would you like help with land surveying, title registration, or property laws?",
                "I'm designed for land-related inquiries. Let me know if you need assistance with those topics!"
            ]
            response = random.choice(response_options)  # Randomly select a fallback response

    return jsonify({"response": response})


if __name__ == "__main__":
    app.run(debug=True)
