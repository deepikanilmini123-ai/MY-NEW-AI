import os
import json
import difflib
from flask import Flask, request, jsonify
from flask_cors import CORS
from duckduckgo_search import DDGS
import firebase_admin
from firebase_admin import credentials, db

# ==========================================
# 1. FIREBASE MANAGER
# ==========================================
class FirebaseManager:
    def __init__(self):
        try:
            if not firebase_admin._apps:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                cred_path = os.path.join(current_dir, "serviceAccountKey.json")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://my-gameing-site-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
            self.db_ref = db.reference()
            self.enabled = True
            print("[Firebase]: Connected to Realtime Database successfully!")
        except Exception as e:
            print(f"[Firebase Warning]: {e}")
            self.enabled = False

    def log_interaction(self, user_input, response):
        if not self.enabled:
            return
        try:
            self.db_ref.child('logs').push({'user': user_input, 'ai': response})
        except Exception as e:
            print(f"[Firebase Log Error]: {e}")

    def add_to_dataset(self, prompt, response):
        if not self.enabled:
            return False
        try:
            self.db_ref.child('dataset').push({'prompt': prompt, 'response': response})
            return True
        except Exception as e:
            print(f"[Firebase Train Error]: {e}")
            return False


# ==========================================
# 2. WEB SEARCH & DATASET ENGINE
# ==========================================
class WebSearchEngine:
    def __init__(self, max_results=2):
        self.max_results = max_results
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.dataset_path = os.path.join(current_dir, "dataset.json")

    def load_dataset(self):
        if not os.path.exists(self.dataset_path):
            return []
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Dataset Load Error]: {e}")
            return []

    def get_best_dataset_match(self, user_input):
        dataset = self.load_dataset()
        if not dataset:
            return None

        user_input_clean = user_input.lower().strip()
        best_match = None
        highest_score = 0.0

        for item in dataset:
            prompt = item.get("prompt", "").lower().strip()
            if not prompt:
                continue

            similarity_score = difflib.SequenceMatcher(None, user_input_clean, prompt).ratio()

            if prompt in user_input_clean or user_input_clean in prompt:
                similarity_score += 0.25

            if similarity_score > highest_score and similarity_score >= 0.55:
                highest_score = similarity_score
                best_match = item.get("response")

        return best_match

    def check_conversational_intent(self, user_input):
        text = user_input.lower().strip()

        identity_keywords = ["kauda oya", "kavuda oya", "oya kauda", "oyage nama", "oyage nama mokakda", "who are you", "who r u", "who r you"]
        if any(k in text for k in identity_keywords) or ("oya" in text and "kauda" in text) or ("kauda" in text and "oya" in text):
            return "මම කවිනු විසින් සාදන ලද Custom Robot AI පද්ධතියක්!"

        if any(w in text for w in ["sinhala", "සිංහල", "sinhala puluwanda", "understand sinhala"]):
            return "ඔවු, මට සිංහල තේරුම් ගන්න සහ සිංහලෙන් පිළිතුරු දෙන්න පුළුවන්!"

        if text in ["hi", "hello", "hey", "halo", "haai", "kohomada", "kohomda"]:
            return "Hello! මම ඔයාගේ Custom Robot AI එක. මට ඔයාට උදව් කරන්නේ කොහොමද?"

        return None

    def add_to_dataset(self, new_prompt, new_response):
        dataset = self.load_dataset()
        dataset.append({
            "prompt": new_prompt.strip(),
            "response": new_response.strip()
        })
        try:
            with open(self.dataset_path, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[Dataset Write Error]: {e}")
            return False

    def search_web(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_results))
                if results:
                    cleaned_results = []
                    for r in results:
                        body = r.get('body', '')
                        if body and len(body) > 30:
                            cleaned_results.append(body)
                    return "\n".join(cleaned_results[:2])
        except Exception as e:
            print(f"[Search Warning]: {e}")
        return None

    def get_search_context(self, user_input):
        dataset_res = self.get_best_dataset_match(user_input)
        if dataset_res:
            return f"[Dataset Answer]: {dataset_res}"

        intent_res = self.check_conversational_intent(user_input)
        if intent_res:
            return f"[Dataset Answer]: {intent_res}"

        if len(user_input.strip().split()) == 1 and len(user_input.strip()) < 5:
            return "[Dataset Answer]: කරුණාකර ඔබේ ප්‍රශ්නය තව ටිකක් පැහැදිලිව අහන්න."

        web_res = self.search_web(user_input)
        if web_res:
            return f"[Web Search Result]:\n{web_res}"

        return "[Dataset Answer]: කණගාටුයි, ඒ පිළිබඳ තොරතුරු සොයා ගැනීමට නොහැකි විය."


# ==========================================
# 3. AI MODEL CORE
# ==========================================
class RobotAIEngine:
    def __init__(self):
        print("[Model Core]: Base Model Layer Online.")

    def generate_response(self, full_context):
        if "[Dataset Answer]:" in full_context:
            return full_context.split("[Dataset Answer]:")[-1].strip()

        if "[Web Search Result]:" in full_context:
            raw_search = full_context.split("[Web Search Result]:")[-1].strip()
            lines = [line.strip() for line in raw_search.split("\n") if line.strip()]
            summary = " ".join(lines[:3])
            if len(summary) > 300:
                summary = summary[:300] + "..."
            return f"අන්තර්ජාලයේ සෙවුම් තොරතුරු අනුව:\n{summary}"

        return "මම ඒ ගැන තවදුරටත් අධ්‍යයනය කරමින් සිටිමි."


# ==========================================
# 4. FLASK API
# ==========================================
app = Flask(__name__)
CORS(app)

firebase = FirebaseManager()
search = WebSearchEngine(max_results=2)
ai = RobotAIEngine()

chat_history = []

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json or {}
    user_input = data.get('message', '').strip()

    if not user_input:
        return jsonify({'response': 'කරුණාකර ප්‍රශ්නයක් ඇතුළත් කරන්න.'})

    if user_input.lower().startswith("you:"):
        user_input = user_input[4:].strip()

    if user_input.lower().startswith("train:"):
        raw_data = user_input[6:].strip()
        if "|" in raw_data:
            prompt, response = raw_data.split("|", 1)
            prompt = prompt.strip()
            response = response.strip()

            if prompt and response:
                json_ok = search.add_to_dataset(prompt, response)
                fb_ok = firebase.add_to_dataset(prompt, response)

                if json_ok or fb_ok:
                    res_msg = f"✅ සාර්ථකයි! dataset.json එකට සහ Firebase එකට සේව් කරගත්තා.\n📌 Prompt: {prompt}\n📌 Response: {response}"
                else:
                    res_msg = "❌ Save කිරීමේදී දෝෂයක් සිදුවුණා."
            else:
                res_msg = "⚠️ කරුණාකර 'train: ප්‍රශ්නය | උත්තරය' ආකෘතියට ටයිප් කරන්න."
        else:
            res_msg = "⚠️ ප්‍රශ්නය සහ උත්තරය වෙන් කිරීමට '|' සංකේතය යොදන්න."

        return jsonify({'response': res_msg})

    search_context = search.get_search_context(user_input)
    full_context = f"Search Context:\n{search_context}\n\nUser Question: {user_input}"

    response = ai.generate_response(full_context)

    chat_history.append({"user": user_input, "ai": response})
    if len(chat_history) > 5:
        chat_history.pop(0)

    firebase.log_interaction(user_input, response)

    return jsonify({'response': response})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 Robot AI API Server is live on port {port}!")
    app.run(host='0.0.0.0', port=port)