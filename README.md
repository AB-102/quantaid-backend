# QuantumAiEdBackEnd

This is the backend service for QuantumAiEd, providing an API for generating AI feedback, storing lessons and readings, and managing user progress. Built using Flask, MongoDB (with GridFS), and the OpenAI API.

---

## ⚙️ Tech Stack

- Python 3.8+
- Flask
- Flask-CORS
- PyMongo + GridFS
- OpenAI API
- dotenv

---

## 🚀 Setup Instructions

1. Clone the repository:

   git clone https://github.com/kevvinnnh/QuantumAiEdBackEnd.git  
   cd QuantumAiEdBackEnd

2. Create and activate a virtual environment:

   python -m venv venv  
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:

   pip install -r requirements.txt

4. Create a `.env` file:

   cp .env.example .env

   Fill in your environment variables:

   FLASK_SECRET_KEY=your_flask_secret_key_here  
   OPENAI_API_KEY=your_openai_api_key_here  
   MONGODB_URI=your_mongodb_connection_string  
   SESSION_COOKIE_SECURE=False  
   CORS_ORIGIN=http://localhost:5173

5. Start the server:

   python app.py

   Your backend will run at http://localhost:5000

---

## 🔐 Admin Routes

Requires session `admin=True`:
- POST /admin/upload_lesson — Upload lesson metadata
- POST /admin/upload_reading — Upload reading w/ image or video to GridFS
- POST /admin/upload_quiz — Upload quiz content

---

## ✍️ Content Routes

- POST /explain_text — Simplify and explain concepts with bullet points
- POST /generate_analogy — Return a relatable analogy for input text
- POST /chat_about_text — Continue a discussion about highlighted concepts
- POST /chat_quiz_question — Provide adaptive feedback on quiz responses

---

## 👤 User & Profile Routes

- POST /append_user_id — Log in user and assign session
- GET /get_user_id — Return logged-in user ID from session
- POST /save_profile — Submit user's background info and hobbies
- GET /get_user_profile — Fetch saved profile data
- POST /logout — Clear user session

---

## 🧠 Quiz & Progress Routes

- POST /save_quiz_result — Save quiz scores and unlock next levels
- GET /get_user_progress — Return list of completed quizzes and levels

---

## 🩺 Health Check

- GET /ping — Check MongoDB connection and app status

---

## 🌐 CORS & Sessions

- CORS allowed origins:
  - http://localhost:5173
  - https://quantum-ai-ed-front-end-smoky.vercel.app

- Session cookies are configured to support cross-origin credentials.
- Admin access is granted based on user ID (e.g., kh78@rice.edu).

---

## 📄 .env.example

Create a file named `.env.example` with the following:

FLASK_SECRET_KEY=your_flask_secret_key_here  
OPENAI_API_KEY=your_openai_api_key_here  
MONGODB_URI=your_mongodb_connection_string  
SESSION_COOKIE_SECURE=False  
CORS_ORIGIN=http://localhost:5173

---

## 🐛 Troubleshooting

- MongoDB: Check `MONGODB_URI` format and permissions.
- OpenAI: Verify `OPENAI_API_KEY` is active and has quota.
- CORS issues: Confirm `CORS_ORIGIN` matches frontend URL.
- Sessions: Ensure `FLASK_SECRET_KEY` is set and cookies are enabled in the browser.

---

## 📄 License

MIT
