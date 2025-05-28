# QuantumAiEdBackEnd

QuantumAiEd is an AI-driven educational platform that generates feedback, analogies, explanations, and personalized quizzes for quantum computing instruction. This repository contains the backend API, built with Flask, OpenAI, and MongoDB, designed to support dynamic educational content generation and progress tracking.

---

## 🌐 Deployed Frontend

🔗 [https://quantum-ai-ed-front-end-smoky.vercel.app/](https://quantum-ai-ed-front-end-smoky.vercel.app/)

---

## 🧰 Tech Stack

- **Backend Framework**: Flask
- **Database**: MongoDB + GridFS
- **AI Integration**: OpenAI API
- **Sessions**: Flask-Session
- **CORS**: Flask-CORS
- **Environment Management**: python-dotenv

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/kevvinnnh/QuantumAiEdBackEnd.git
cd QuantumAiEdBackEnd
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with the following keys:

```
FLASK_SECRET_KEY=your_flask_secret_key
OPENAI_API_KEY=your_openai_api_key
MONGODB_URI=your_mongodb_connection_uri
SESSION_COOKIE_SECURE=False
CORS_ORIGIN=http://localhost:5173
```

### 5. Run the Server

```bash
python app.py
```

Server will be live at:  
📍 `http://localhost:5000`

---

## 🔐 Admin Routes

> Requires session with `admin=True`

| Endpoint               | Description                        |
|------------------------|------------------------------------|
| `POST /admin/upload_lesson`  | Upload lesson metadata         |
| `POST /admin/upload_reading` | Upload reading media to GridFS |
| `POST /admin/upload_quiz`    | Upload quiz content            |

---

## ✍️ Content Generation Routes

| Endpoint                 | Description                                  |
|--------------------------|----------------------------------------------|
| `POST /explain_text`     | Simplify input and return bullet explanations |
| `POST /generate_analogy` | Return analogy for abstract input             |
| `POST /chat_about_text`  | Engage in dialog about a concept              |
| `POST /chat_quiz_question` | Feedback on quiz answers with context      |

---

## 👤 User & Profile Routes

| Endpoint               | Description                            |
|------------------------|----------------------------------------|
| `POST /append_user_id` | Log in and start session               |
| `GET /get_user_id`     | Return user ID from session            |
| `POST /save_profile`   | Save user background info              |
| `GET /get_user_profile`| Retrieve saved profile data            |
| `POST /logout`         | End session and clear user context     |

---

## 🧠 Quiz & Progress Routes

| Endpoint                 | Description                             |
|--------------------------|-----------------------------------------|
| `POST /save_quiz_result` | Save quiz score and unlock new levels   |
| `GET /get_user_progress` | Retrieve completed quizzes and progress |

---

## 🩺 Health Check

| Endpoint    | Description                      |
|-------------|----------------------------------|
| `GET /ping` | Check MongoDB and app connectivity |

---

## 🌍 CORS & Session Configuration

- Allowed frontend origins:
  - `http://localhost:5173`
  - `https://quantum-ai-ed-front-end-smoky.vercel.app`
- Session cookies support cross-origin credentials
- Admin access is restricted to predefined email IDs

---

## 🧪 `.env.example`

```env
FLASK_SECRET_KEY=your_flask_secret_key
OPENAI_API_KEY=your_openai_api_key
MONGODB_URI=your_mongodb_connection_string
SESSION_COOKIE_SECURE=False
CORS_ORIGIN=http://localhost:5173
```

---

## 🐛 Troubleshooting

- 🔌 **MongoDB connection**: Check URI format and database access.
- 🔐 **OpenAI access**: Ensure API key is valid and usage quota is sufficient.
- ⚠️ **CORS errors**: Confirm the frontend origin matches `CORS_ORIGIN`.
- 🍪 **Sessions**: Use a secure and unique `FLASK_SECRET_KEY`; confirm cookies are enabled in the browser.

---

## 📄 License

MIT

---

## 📚 Citation

If referencing QuantumAiEd in academic work, please cite:

> Kevin Hernandez, Tirthak Patel.  
> *Enhancing Early Quantum Computing Education with QuantumAiEd: Bridging the Educational Gap.*  
> SIGCSETS 2025: Proceedings of the 56th ACM Technical Symposium on Computer Science Education V. 2, p. 1755.  
> [https://doi.org/10.1145/3641555.3705028](https://doi.org/10.1145/3641555.3705028)  
> Published: February 18, 2025. ACM.
