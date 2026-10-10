import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

# ==========================================
# 1. FLASK APP & ROBUST CORS SETUP
# ==========================================
app = Flask(__name__)
CORS(app)  # Enable CORS globally

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, PUT, POST, DELETE, OPTIONS')
    return response

# ==========================================
# 2. FIREBASE INITIALIZATION
# ==========================================
try:
    if not firebase_admin._apps:
        cred_path = 'serviceAccountKey.json'
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://my-new-ai-default-rtdb.firebaseio.com/'
            })
            print("[Firebase]: Connected to Realtime Database successfully!")
        else:
            print("[Firebase Warning]: serviceAccountKey.json not found!")
except Exception as e:
    print(f"[Firebase Error]: {e}")

# ==========================================
# 3. LOAD DATASET
# ==========================================
DATASET = {}
dataset_path = 'dataset.json'
if os.path.exists(dataset_path):
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            DATASET = json.load(f)
        print("[Dataset]: dataset.json loaded successfully!")
    except Exception as e:
        print(f"[Dataset Error]: {e}")

# ==========================================
# 4. API ROUTES
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Active", "message": "Custom Robot AI Backend is running!"})

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    # Handle preflight OPTIONS request explicitly
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200

    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'response': 'කරුණාකර ප්‍රශ්නයක් යොමු කරන්න.'}), 400

        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'response': 'හිස් පණිවිඩයක් ලැබී ඇත.'}), 400

        # Training feature: "train: question | answer"
        if user_message.lower().startswith('train:'):
            parts = user_message[6:].split('|')
            if len(parts) == 2:
                q = parts[0].strip().lower()
                ans = parts[1].strip()
                DATASET[q] = ans
                
                # Save to local dataset.json
                try:
                    with open(dataset_path, 'w', encoding='utf-8') as f:
                        json.dump(DATASET, f, ensure_ascii=False, indent=4)
                except Exception as ex:
                    print(f"Dataset save error: {ex}")

                # Save to Firebase Realtime Database
                try:
                    ref = db.reference('custom_ai/dataset')
                    ref.update({q.replace('.', '_'): ans})
                except Exception as ex:
                    print(f"Firebase save error: {ex}")

                return jsonify({'response': f'ස්තුතියි! මම අලුත් ප්‍රශ්නය ඉගෙන ගත්තා: "{parts[0].strip()}"'})
            else:
                return jsonify({'response': 'වැරදි ආකෘතියකි. භාවිතය: train: ප්‍රශ්නය | උත්තරය'})

        # Dataset matching logic
        response_text = "මට ඒ ගැන පැහැදිලි නැහැ. 'train: ප්‍රශ්නය | උත්තරය' ලෙස මට අලුත් දේවල් උගන්වන්න පුළුවන්!"
        
        user_msg_lower = user_message.lower()
        if user_msg_lower in DATASET:
            response_text = DATASET[user_msg_lower]
        else:
            for key, val in DATASET.items():
                if key in user_msg_lower or user_msg_lower in key:
                    response_text = val
                    break

        # Log chat to Firebase
        try:
            ref = db.reference('custom_ai/chats')
            ref.push({
                'user': user_message,
                'bot': response_text
            })
        except Exception as ex:
            print(f"Firebase chat log error: {ex}")

        return jsonify({'response': response_text})

    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({'response': 'සර්වර් එකේ දෝෂයක් සිදු විය.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
