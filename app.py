import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS, cross_origin # Keep cross_origin import
from pymongo.mongo_client import MongoClient
from pymongo.errors import PyMongoError
from gridfs import GridFS
from openai import OpenAI
from flask import abort
from datetime import datetime, timezone
from functools import wraps


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True # Assuming HTTPS eventually or for Vercel<->Render

# Global CORS configuration (applied to all routes unless overridden by @cross_origin)
CORS(
    app,
    origins=[
      "http://localhost:5173",
      "https://quantum-ai-ed-front-end-smoky.vercel.app"
    ],
    supports_credentials=True,
    # Allow common headers, "*" is okay for dev but be more specific in prod if possible
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# --- OpenAI client ---
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Mongo Setup ---
uri = os.getenv("MONGODB_URI")
mongo_client = MongoClient(uri)
db = mongo_client.get_database("QuantumAiEd")
fs = GridFS(db)


# --- Routes ---



def admin_required(func):
    def wrapper(*args, **kwargs):
        # For preflight requests, bypass the admin check
        if request.method == 'OPTIONS':
            # Create a proper empty response with 200 status.
            return make_response(jsonify({'message': 'OK'}), 200)
        if not session.get('admin', False):
            return jsonify({'error': 'Unauthorized'}), 403
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.method == 'OPTIONS':
            return make_response(jsonify({'message': 'OK'}), 200)
        if not session.get('user_id'):
            return jsonify({'error': 'User not logged in'}), 401
        return func(*args, **kwargs)
    return wrapper

@app.route('/admin/upload_lesson', methods=['POST', 'OPTIONS'])
@admin_required
@cross_origin(supports_credentials=True)  # Ensure CORS wraps the response from admin_required
def upload_lesson():
    # No need to check for OPTIONS here since the decorator handles it.
    try:
        data = request.json or {}
        lesson = {
            'title': data.get('title'),
            'description': data.get('description'),
            'readings': data.get('readings', []),
            'quiz': data.get('quiz', None),
            'created_at': datetime.utcnow()
        }
        db.lessons.insert_one(lesson)
        return jsonify({'message': 'Lesson uploaded successfully'}), 200
    except Exception as e:
        print("Error uploading lesson:", e)
        return jsonify({'error': str(e)}), 500
@app.route('/admin/upload_reading', methods=['POST', 'OPTIONS'])
@admin_required
def upload_reading():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        # For file uploads, use request.files and GridFS
        title = request.form.get('title')
        content = request.form.get('content')
        # Files: images/videos may be uploaded in request.files
        image_id = None
        video_id = None
        if 'image' in request.files:
            image_file = request.files['image']
            image_id = fs.put(image_file, filename=image_file.filename)
        if 'video' in request.files:
            video_file = request.files['video']
            video_id = fs.put(video_file, filename=video_file.filename)
        reading = {
            'title': title,
            'content': content,
            'image_id': image_id,
            'video_id': video_id,
            'created_at': datetime.utcnow()
        }
        db.readings.insert_one(reading)
        return jsonify({'message': 'Reading uploaded successfully'}), 200
    except Exception as e:
        print("Error uploading reading:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/admin/upload_quiz', methods=['POST', 'OPTIONS'])
@admin_required
def upload_quiz():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        # Expecting quiz data: list of questions (each with options and correct answer)
        quiz = {
            'questions': data.get('questions'),
            'created_at': datetime.utcnow()
        }
        db.quizzes.insert_one(quiz)
        return jsonify({'message': 'Quiz uploaded successfully'}), 200
    except Exception as e:
        print("Error uploading quiz:", e)
        return jsonify({'error': str(e)}), 500

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
@cross_origin(origins=[
    "http://localhost:5173",
    "https://quantum-ai-ed-front-end-smoky.vercel.app"
], supports_credentials=True)
def explain_text():
    # no special OPTIONS case needed — Flask‑CORS will reply automatically
    data = request.json or {}
    text = data.get('text')
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
                "You are an expert quantum computing tutor who excels at making complex concepts accessible. "
                "Your explanations should be:\n"
                "- Clear and detailed (200-300 words)\n"
                "- Use specific examples and analogies when helpful\n"
                "- Break down complex ideas into digestible steps\n"
                "- Use bullet points for key concepts\n"
                "- End by checking understanding or offering to clarify further\n"
                "- Be engaging and encouraging"
            )
        }
        user_msg = {
            "role": "user",
            "content": (
                f"Please provide a detailed explanation of this quantum computing concept:\n\n"
                f'"{text}"\n\n'
                f"Structure your response (but without actually using number or bullet lists) as:\n"
                f"1. A brief overview of what this concept is\n"
                f"2. Key points broken down with bullet points\n"
                f"3. A concrete example or analogy if applicable\n"
                f"4. Why this concept matters in quantum computing\n"
                f"5. Ask if anything needs clarification"
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
@cross_origin(origins=[
    "http://localhost:5173",
    "https://quantum-ai-ed-front-end-smoky.vercel.app"
], supports_credentials=True)
def chat_about_text():
    # no special OPTIONS case needed — Flask‑CORS will reply automatically
    data = request.json or {}
    text = data.get('text')
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
@login_required
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


@app.route('/generate_analogy', methods=['POST', 'OPTIONS'])
@login_required
@cross_origin(origins=[
    "http://localhost:5173",
    "https://quantum-ai-ed-front-end-smoky.vercel.app"
], supports_credentials=True)
def generate_analogy():
    # no special OPTIONS case needed — Flask‑CORS will reply automatically
    data = request.json or {}
    text = data.get('text')
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'No text provided for analogy'}), 400

        # Mirror explain endpoint but with analogy prompt
        system_prompt = {
            'role': 'system',
            'content': (
                "Create clear, relatable analogies for quantum computing concepts using everyday objects. "
                "Keep responses 200-250 words. Use simple language and direct comparisons. "
                "Structure: introduce analogy, explain the parallel, connect back to quantum concept."
            )
        }
        user_prompt = {
            'role': 'user',
            'content': (
                f"Create a clear analogy for this quantum concept using an everyday scenario:\n\n"
                f'"{text}"\n\n'
                f"Use simple language and explain how the analogy relates to the quantum concept. "
                f"Keep it engaging but concise."
            )
        }
        messages = [system_prompt, user_prompt]

        response = openai_client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=messages,
            max_tokens=250,
            temperature=0.7
        )
        analogy = response.choices[0].message.content.strip()
        return jsonify({'analogy': analogy}), 200
    except Exception as e:
        print('Error in /generate_analogy:', e)
        return jsonify({'error': str(e)}), 500

@app.route('/append_user_id', methods=['POST']) # Removed OPTIONS from methods list here
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def append_user_id():
    # REMOVED: if request.method == 'OPTIONS': ... block
    try:
        # ... (rest of your POST logic remains the same)
        data = request.json or {}
        email = data.get('user_id')
        name = data.get('name')
        picture = data.get('picture')
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        email = email.lower()
        if email == 'kh78@rice.edu':
            session['admin'] = True
        else:
            session['admin'] = False

        # Force test email to always go through onboarding
        if email == 'soccerdudesoccerdude@gmail.com':
            session['user_id'] = email
            print(f"DEBUG: Test user {email} forced to onboarding.")
            return jsonify({'message': 'Test user - redirecting to onboarding', 'redirect_to': 'profile-creation'}), 200

        existing_user = db.users.find_one({'user_id': email})
        if existing_user:
            session['user_id'] = email
            print(f"DEBUG: User {email} logged in. Session ID set.")
            if existing_user.get('profile_complete'):
                print(f"DEBUG: User {email} exists and profile is complete.")
                return jsonify({'message': 'User exists and profile is complete', 'redirect_to': 'map'}), 200
            else:
                print(f"DEBUG: User {email} exists but profile incomplete.")
                return jsonify({'message': 'User exists but profile incomplete', 'redirect_to': 'profile-creation'}), 200
        else:
            new_user_data = {
                'user_id': email, 'name': name, 'picture': picture,
                'profile_complete': False, 'unlockedLevels': [0],
                'completedQuizzes': [], 'createdAt': datetime.now(timezone.utc)
            }
            db.users.insert_one(new_user_data)
            session['user_id'] = email
            print(f"DEBUG: New user {email} created. Session ID set.")
            return jsonify({'message': 'User data saved to MongoDB', 'redirect_to': 'profile-creation'}), 201
    except PyMongoError as e:
        print(f"Error in /append_user_id (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error in /append_user_id: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

@app.route('/get_user_id', methods=['GET']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def get_user_id():
    # REMOVED: if request.method == 'OPTIONS': ... block
    uid = session.get('user_id')
    print("DEBUG: GET /get_user_id -> session['user_id'] =", uid)
    if not uid:
        return jsonify({'error': 'User ID not found in session'}), 401
    return jsonify({'user_id': uid}), 200

@app.route('/save_profile', methods=['POST']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def save_profile():
    # REMOVED: if request.method == 'OPTIONS': ... block
    user_id = session.get('user_id')
    # ... (rest of your POST logic remains the same)
    if not user_id:
        return jsonify({'error': 'User not logged in. Please log in again.'}), 401
    try:
        data = request.json or {}
        print(f"DEBUG: Received data in /save_profile for user {user_id} =>", data)
        user_doc = db.users.find_one({'user_id': user_id})
        if not user_doc:
            session.pop('user_id', None)
            return jsonify({'error': f"User not found with ID={user_id}. Please log in again."}), 404
        major = data.get('other_major') if data.get('other_major') else data.get('college_major')
        hobbies = data.get('favoriteHobbies', [])
        if not isinstance(hobbies, list):
            hobbies = [str(hobbies)] if hobbies else []
        profile_data = {
            'education_level': data.get('educationLevel'), 'major': major,
            'knows_quantum_computing': data.get('knowsQuantumComputing'),
            'coding_experience': data.get('codingExperience'),
            'favorite_hobbies': hobbies,
            'use_generic_analogies': data.get('use_generic_analogies', True)
        }
        print("DEBUG: Constructed profile_data =>", profile_data)
        update_result = db.users.update_one(
            {'user_id': user_id},
            {'$set': {
                'profile': profile_data, 'profile_complete': True,
                'profileLastUpdatedAt': datetime.now(timezone.utc)
            }}
        )
        if update_result.matched_count == 0:
             return jsonify({'error': f"Failed to find user {user_id} during update."}), 404
        if update_result.modified_count == 0 and update_result.matched_count == 1:
            print(f"DEBUG: Profile data for {user_id} submitted but no changes were detected.")
            return jsonify({'message': 'Profile data submitted, but no changes needed.'}), 200
        print(f"DEBUG: Profile for user {user_id} saved successfully.")
        return jsonify({'message': 'Profile data saved successfully'}), 200
    except PyMongoError as e:
        print(f"Error in /save_profile (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error in /save_profile: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500


@app.route('/get_user_profile', methods=['GET']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def get_user_profile():
    # REMOVED: if request.method == 'OPTIONS': ... block
    user_id = session.get('user_id')
    # ... (rest of your GET logic remains the same)
    if not user_id:
        return jsonify({'error': 'User ID not found in session'}), 401
    try:
        user = db.users.find_one(
            {'user_id': user_id},
            {'_id': 0, 'profile': 1, 'name': 1, 'picture': 1}
        )
        if not user:
            session.pop('user_id', None)
            return jsonify({'error': 'User profile not found'}), 404
        profile = user.get('profile', {})
        if not profile or not user.get('profile_complete'):
            return jsonify({'error': 'Profile data missing or incomplete for user'}), 404
        response_data = {
            'name': user.get('name', 'User'), 'profilePicture': user.get('picture', ''),
            'educationLevel': profile.get('education_level', 'Not provided'),
            'major': profile.get('major', 'Not provided'),
            'favoriteHobbies': profile.get('favorite_hobbies', []),
            'use_generic_analogies': profile.get('use_generic_analogies', True)
        }
        return jsonify(response_data), 200
    except PyMongoError as e:
        print(f"Error in /get_user_profile (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error in /get_user_profile: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

@app.route('/logout', methods=['POST']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def logout():
    # REMOVED: if request.method == 'OPTIONS': ... block
    user_id = session.get('user_id')
    # ... (rest of your POST logic remains the same)
    if user_id:
        print(f"DEBUG: Logging out user {user_id}")
        session.pop('user_id', None)
        session.pop('admin', None)
        return jsonify({'message': 'Logged out successfully'}), 200
    else:
        print("DEBUG: Logout called but no user was logged in.")
        return jsonify({'message': 'No user session found to log out'}), 200

@app.route('/save_quiz_result', methods=['POST']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def save_quiz_result():
    # REMOVED: if request.method == 'OPTIONS': ... block
    user_id = session.get('user_id')
    # ... (rest of your POST logic remains the same)
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401
    try:
        data = request.json
        if not data or 'courseId' not in data or 'score' not in data or 'passed' not in data:
            return jsonify({'error': 'Missing required quiz data (courseId, score, passed)'}), 400
        course_id = data['courseId']
        score = data['score']
        passed = data['passed']
        timestamp = datetime.now(timezone.utc)
        if not isinstance(course_id, int) or not isinstance(score, (int, float)) or not isinstance(passed, bool):
             return jsonify({'error': 'Invalid data types for quiz data'}), 400
        quiz_result_doc = {
            "courseId": course_id, "score": score, "passed": passed, "timestamp": timestamp
        }
        update_operations = {
            '$push': { 'completedQuizzes': quiz_result_doc },
             '$set': { 'lastActivityAt': timestamp }
        }
        MAX_COURSE_ID = 8
        if passed and course_id < MAX_COURSE_ID:
            next_level_id = course_id + 1
            update_operations['$addToSet'] = { 'unlockedLevels': next_level_id }
        result = db.users.update_one( {'user_id': user_id}, update_operations )
        if result.matched_count == 0:
            return jsonify({'error': 'User not found during quiz save'}), 404
        print(f"DEBUG: Quiz result saved for user {user_id}, course {course_id}. Passed: {passed}")
        updated_user = db.users.find_one({'user_id': user_id}, {'_id': 0, 'unlockedLevels': 1})
        new_unlocked_levels = updated_user.get('unlockedLevels', [0]) if updated_user else [0]
        return jsonify({
            'message': 'Quiz result saved successfully',
            'unlockedLevels': new_unlocked_levels
            }), 200
    except PyMongoError as e:
        print(f"Error saving quiz result (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error saving quiz result: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

@app.route('/get_user_progress', methods=['GET']) # Removed OPTIONS
@cross_origin(supports_credentials=True) # Decorator handles OPTIONS
def get_user_progress():
    # REMOVED: if request.method == 'OPTIONS': ... block
    user_id = session.get('user_id')
    # ... (rest of your GET logic remains the same)
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401
    try:
        user = db.users.find_one(
            {'user_id': user_id},
            {'_id': 0, 'unlockedLevels': 1, 'completedQuizzes': 1}
        )
        if not user:
            session.pop('user_id', None)
            return jsonify({'error': 'User data not found for this session'}), 404
        unlocked_levels = user.get('unlockedLevels', [0])
        completed_quizzes = user.get('completedQuizzes', [])
        print(f"DEBUG: Fetched progress for user {user_id}: Unlocked {unlocked_levels}")
        return jsonify({
            'unlockedLevels': unlocked_levels,
            'completedQuizzes': completed_quizzes
            }), 200
    except PyMongoError as e:
        print(f"Error fetching user progress (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error fetching user progress: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

@app.route('/ping', methods=['GET'])
# No @cross_origin needed if it doesn't require credentials or special headers
def ping():
    try:
        mongo_client.admin.command('ping')
        db_status = "connected"
    except Exception as e:
        db_status = f"error ({e})"
    return jsonify({'status': 'pong', 'database': db_status}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use debug=True for development to get auto-reloading and better error pages
    # Ensure debug=False in production
    app.run(host='0.0.0.0', port=port, debug=False)