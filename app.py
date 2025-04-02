import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from gridfs import GridFS
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

# Use the secret key from the environment; fallback to a random key (only for dev)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

# Cookie settings (adjust SESSION_COOKIE_SECURE to True in production with HTTPS)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if serving over HTTPS in production

CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:5173", 
        "https://quantum-ai-ed-front-end-smoky.vercel.app"
    ]}},
    supports_credentials=True,
    allow_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"]
)

###############################################################################
# OpenAI client
###############################################################################
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

###############################################################################
# Mongo Setup
###############################################################################
# Use the MongoDB URI from the environment (do not hardcode credentials)
uri = os.getenv("MONGODB_URI")
mongo_client = MongoClient(uri)
db = mongo_client.get_database("QuantumAiEd")
fs = GridFS(db)

###############################################################################
# HELPER: get_user_hobbies
###############################################################################
def get_user_hobbies(user_id: str):
    user_doc = db.users.find_one({'user_id': user_id}, {'_id': 0, 'profile': 1})
    if not user_doc:
        print("DEBUG: No user document found for user_id =", user_id)
        return []
    profile = user_doc.get('profile', {})
    hobbies = profile.get('favorite_hobbies', [])
    print(f"DEBUG: Hobbies for user_id {user_id}:", hobbies)
    return hobbies

###############################################################################
# EXPLAIN TEXT
###############################################################################
@app.route('/explain_text', methods=['POST', 'OPTIONS'])
def explain_text():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        text = data.get('text')
        if not text:
            return jsonify({'error': 'No text provided'}), 400

        user_id = session.get('user_id')
        if not user_id:
            hobby_context = "No user logged in; use generic analogies."
        else:
            hobby_context = "Use generic analogies (e.g., coin toss for superposition)."

        system_prompt = {
            "role": "system",
            "content": (
                "You are a friendly quantum computing tutor. Use bullet points in a concise, engaging manner, ask if the student understands."
            )
        }
        user_msg = {
            "role": "user",
            "content": (
                f"Explain and simplify this text in a beginner-friendly way:\n\n{text}\n\n"
                "Make sure to be concise and use bullet points."
            )
        }
        messages = [system_prompt, user_msg]
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=250,
            temperature=0.6
        )
        explanation = response.choices[0].message.content.strip()
        return jsonify({'explanation': explanation}), 200
    except Exception as e:
        print("Error in /explain_text:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# CHAT ABOUT TEXT (Highlight-based)
###############################################################################
@app.route('/chat_about_text', methods=['POST', 'OPTIONS'])
def chat_about_text():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        highlighted_text = data.get('highlighted_text', '')
        conversation_history = data.get('messages', [])
        if not highlighted_text:
            highlighted_text = "(No specific highlighted text, user wants a general chat.)"

        system_prompt = {
            "role": "system",
            "content": (
                "You are a concise quantum tutor. Use bullet points, ask if the student understands, and provide an extra example at the end."
            )
        }
        user_msg = {
            "role": "user",
            "content": f"Discuss the highlighted text: '{highlighted_text}'."
        }
        messages = [system_prompt, user_msg] + conversation_history
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.6
        )
        bot_reply = response.choices[0].message.content.strip()
        return jsonify({'assistant_reply': bot_reply}), 200
    except Exception as e:
        print("Error in /chat_about_text:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# CHAT ABOUT QUIZ QUESTION
###############################################################################
@app.route('/chat_quiz_question', methods=['POST', 'OPTIONS'])
def chat_quiz_question():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        question_text = data.get('question_text', '')
        conversation_history = data.get('messages', [])
        is_correct = data.get('isCorrect', None)  # New field
        selected_answer = data.get('selectedAnswer', '')
        correct_answer = data.get('correctAnswer', '')

        if not question_text:
            return jsonify({'error': 'No question_text provided'}), 400

        system_instructions = "You are a helpful quantum tutor. Use bullet points and clear language. "
        if is_correct is True:
            system_instructions += (
                f"The student answered correctly. Their answer was: \"{selected_answer}\" which is correct because \"{correct_answer}\". "
                "Provide a detailed explanation reinforcing why that answer is correct and highlighting key concepts."
            )
        elif is_correct is False:
            system_instructions += (
                f"The student answered incorrectly. Their answer was: \"{selected_answer}\" but the correct answer is: \"{correct_answer}\". "
                "Explain common misconceptions and clearly detail why the correct answer is right."
            )
        else:
            system_instructions += "Provide a concise explanation of the question."
        system_prompt = {
            "role": "system",
            "content": system_instructions,
        }
        user_msg = {
            "role": "user",
            "content": f"Help me understand this quiz question:\n{question_text}"
        }
        messages = [system_prompt, user_msg] + conversation_history

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=350,
            temperature=0.6
        )
        bot_reply = response.choices[0].message.content.strip()
        return jsonify({'assistant_reply': bot_reply}), 200
    except Exception as e:
        print("Error in /chat_quiz_question:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# APPEND USER ID
###############################################################################
@app.route('/append_user_id', methods=['POST', 'OPTIONS'])
def append_user_id():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        email = data.get('user_id')
        name = data.get('name')
        picture = data.get('picture')
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        existing_user = db.users.find_one({'user_id': email})
        if existing_user:
            session['user_id'] = email
            if existing_user.get('profile_complete'):
                print("DEBUG: session['user_id'] set to:", email)
                return jsonify({'message': 'User exists and profile is complete', 'redirect_to': 'map'}), 200
            else:
                print("DEBUG: session['user_id'] set to:", email)
                return jsonify({'message': 'User exists but profile incomplete', 'redirect_to': 'profile-creation'}), 200
        else:
            db.users.insert_one({
                'user_id': email,
                'name': name,
                'picture': picture,
                'profile_complete': False,
                'unlockedLevels': [0],
                'completedQuizzes': []
            })
            session['user_id'] = email
            print("DEBUG: session['user_id'] set to (new user):", email)
            return jsonify({'message': 'User data saved to MongoDB', 'redirect_to': 'profile-creation'}), 201
    except Exception as e:
        print("Error in /append_user_id:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# GET USER ID
###############################################################################
@app.route('/get_user_id', methods=['GET', 'OPTIONS'])
def get_user_id():
    if request.method == 'OPTIONS':
        return '', 200
    uid = session.get('user_id')
    print("DEBUG: GET /get_user_id -> session['user_id'] =", uid)
    if not uid:
        return jsonify({'error': 'User ID not found in session'}), 404
    return jsonify({'user_id': uid}), 200

###############################################################################
# SAVE PROFILE
###############################################################################
@app.route('/save_profile', methods=['POST', 'OPTIONS'])
def save_profile():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        print("DEBUG: Received data in /save_profile =>", data)
        user_id = data.get('user_id', '').strip() or session.get('user_id')
        if not user_id:
            return jsonify({'error': 'No valid user_id found in data or session. Please log in again.'}), 401
        user_doc = db.users.find_one({'user_id': user_id})
        if not user_doc:
            return jsonify({'error': f"No user found with user_id={user_id}"}), 404
        major = data.get('other_major') if data.get('other_major') else data.get('college_major')
        profile_data = {
            'education_level': data.get('educationLevel'),
            'major': major,
            'knows_quantum_computing': data.get('knowsQuantumComputing'),
            'coding_experience': data.get('codingExperience'),
            'favorite_hobbies': data.get('favoriteHobbies', []),
            'use_generic_analogies': data.get('use_generic_analogies', True)
        }
        print("DEBUG: Constructed profile_data =>", profile_data)
        if not isinstance(profile_data['favorite_hobbies'], list):
            return jsonify({'error': 'favoriteHobbies must be an array/list'}), 400
        db.users.update_one(
            {'user_id': user_id},
            {'$set': {
                'profile': profile_data,
                'profile_complete': True
            }},
            upsert=True
        )
        return jsonify({'message': 'Profile data saved successfully'}), 200
    except Exception as e:
        print("Error in /save_profile:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# GET USER PROFILE
###############################################################################
@app.route('/get_user_profile', methods=['GET', 'OPTIONS'])
def get_user_profile():
    if request.method == 'OPTIONS':
        return '', 200
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID not found in session'}), 404
    try:
        user = db.users.find_one({'user_id': user_id}, {'_id': 0, 'profile': 1, 'name': 1, 'picture': 1})
        if not user:
            return jsonify({'error': 'User profile not found'}), 404
        profile = user.get('profile', {})
        if not profile:
            return jsonify({'error': 'Profile data missing for user'}), 404
        return jsonify({
            'name': user.get('name', 'User'),
            'profilePicture': user.get('picture', ''),
            'educationLevel': profile.get('education_level', 'Not provided'),
            'major': profile.get('major', 'Not provided'),
            'favoriteHobbies': profile.get('favorite_hobbies', []),
            'use_generic_analogies': profile.get('use_generic_analogies', True)
        }), 200
    except Exception as e:
        print("Error in /get_user_profile:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# LOGOUT
###############################################################################
@app.route('/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return '', 200
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

###############################################################################
# GET QUIZ PROGRESS
###############################################################################
@app.route('/get_quiz_progress', methods=['GET', 'OPTIONS'])
def get_quiz_progress():
    if request.method == 'OPTIONS':
        return '', 200
    user_id = session.get('user_id')
    if not user_id:
        print("get_quiz_progress: No user_id in session")
        return jsonify({'error': 'User not logged in'}), 401
    try:
        user = db.users.find_one(
            {'user_id': user_id},
            {'_id': 0, 'unlockedLevels': 1, 'completedQuizzes': 1}
        )
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({
            'unlockedLevels': user.get('unlockedLevels', [0]),
            'completedQuizzes': user.get('completedQuizzes', [])
        }), 200
    except Exception as e:
        print("Error in /get_quiz_progress:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# SAVE QUIZ PROGRESS
###############################################################################
@app.route('/save_quiz_progress', methods=['POST', 'OPTIONS'])
def save_quiz_progress():
    if request.method == 'OPTIONS':
        return '', 200
    user_id = session.get('user_id')
    if not user_id:
        print("save_quiz_progress: No user_id in session -> 401")
        return jsonify({'error': 'User not logged in'}), 401
    try:
        data = request.json
        completed_quiz = data.get('completedQuiz')
        unlock_quiz = data.get('unlockQuiz')
        if completed_quiz is None or unlock_quiz is None:
            return jsonify({'error': 'Both completedQuiz and unlockQuiz are required'}), 400
        db.users.update_one(
            {'user_id': user_id},
            {'$addToSet': {'completedQuizzes': completed_quiz}}
        )
        db.users.update_one(
            {'user_id': user_id},
            {'$addToSet': {'unlockedLevels': unlock_quiz}}
        )
        return jsonify({'message': 'Quiz progress saved successfully'}), 200
    except Exception as e:
        print("Error in /save_quiz_progress:", e)
        return jsonify({'error': str(e)}), 500

###############################################################################
# NEW ENDPOINT: GENERATE ANALOGY
###############################################################################
@app.route('/generate_analogy', methods=['POST', 'OPTIONS'])
def generate_analogy():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        last_message = data.get('text', '')
        user_id = session.get('user_id')
        hobby_context = "Use generic analogies."
        if user_id:
            user_doc = db.users.find_one({'user_id': user_id}, {'_id': 0, 'profile': 1})
            if user_doc and 'profile' in user_doc:
                profile = user_doc['profile']
                hobbies = profile.get('favorite_hobbies', [])
                if hobbies:
                    hobby_str = ", ".join(hobbies)
                    hobby_context = f"Use analogies related to these hobbies: {hobby_str}."
        prompt = (
            f"Based on the following content, provide an analogy related to the user's hobbies.\n"
            f"Content: {last_message}\n"
            f"{hobby_context}\n"
            "Provide only the analogy in a concise manner."
        )
        system_prompt = {
            "role": "system",
            "content": "You are a creative assistant who provides helpful analogies when requested."
        }
        user_msg = {
            "role": "user",
            "content": prompt
        }
        messages = [system_prompt, user_msg]
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        analogy = response.choices[0].message.content.strip()
        return jsonify({'analogy': analogy}), 200
    except Exception as e:
        print("Error in /generate_analogy:", e)
        return jsonify({'error': str(e)}), 500
    
@app.route('/ping', methods=['GET'])
def ping():
    return 'pong', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
