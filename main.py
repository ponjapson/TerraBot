from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import difflib
import os
import logging
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

# Fetch response from OpenAI
def get_openai_response(user_message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
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

    if response is None:
        response = get_openai_response(user_message)

    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
