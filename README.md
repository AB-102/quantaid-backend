# Quantaid Backend

Backend API for Quantaid, an AI-driven quantum computing education platform educational platform that generates feedback, analogies, explanations, and personalized quizzes for quantum computing instruction built at Rice University. Serves a React/Vite frontend with personalized lesson content, quizzes, and AI-powered explanations.

## Deployed Frontend

[https://quantum-ai-ed-front-end-smoky.vercel.app/](https://quantum-ai-ed-front-end-smoky.vercel.app/)

## Tech Stack

- **Framework:** Flask (Python)
- **Database:** MongoDB Atlas (pymongo) + GridFS for file storage
- **Auth:** Flask-Login + Argon2id password hashing + session-based with `login_id` invalidation
- **AI:** OpenAI API (explanations, analogies, quiz feedback, chat)
- **Rate Limiting:** Flask-Limiter (5/min on auth endpoints)
- **Email:** Resend (password reset emails)
- **CORS:** Flask-CORS with configurable origins

## Setup

### 1. Clone and install

```bash
git clone https://github.com/kevvinnnh/QuantumAiEdBackEnd.git
cd QuantumAiEdBackEnd
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials. Required variables:

| Variable | Description |
|----------|-------------|
| `FLASK_SECRET_KEY` | Random secret for session signing |
| `OPENAI_API_KEY` | OpenAI API key |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `ADMIN_EMAILS` | Comma-separated admin email addresses |
| `RESEND_API_KEY` | Resend API key for password reset emails |
| `FROM_EMAIL` | Sender address for outbound emails |

Optional variables (sensible defaults provided):

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_LIFETIME_MINUTES` | `10080` (7 days) | Session expiry duration |
| `CORS_ORIGINS` | localhost + Vercel | Comma-separated allowed origins |
| `FRONTEND_URL` | `http://localhost:5173` | Used in password reset email links |
| `FIRST_TIME_USER_EMAIL` | — | Forces this email through onboarding (dev/testing) |

### 3. Run

```bash
python app.py
```

Server starts at `http://localhost:5000`. The frontend expects `VITE_BACKEND_URL=http://localhost:5000`.

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
QuantumAiEdBackEnd/
├── app.py                     # Flask app, CORS, Flask-Login, rate limiter, blueprint registration
├── config.py                  # Centralized settings from .env
├── requirements.txt
├── .env / .env.example
├── routes/
│   ├── __init__.py            # Shared admin_required decorator
│   ├── auth.py                # /auth/* — signup, login, check, logout, password reset/change
│   ├── users.py               # Google SSO login, profile CRUD, profile picture upload
│   ├── progress.py            # Quiz results, lesson progress
│   ├── content.py             # Admin content upload (lessons, readings, quizzes)
│   ├── feedback.py            # User feedback submissions and admin review
│   ├── ai.py                  # AI endpoints with hobby-based personalization
│   └── admin_users.py         # Admin user management (list, disable/enable)
├── services/
│   ├── auth_service.py        # Argon2 hashing, login_id rotation, account lockout, password reset tokens
│   └── email_service.py       # Resend integration for password reset emails
├── database/
│   └── mongo.py               # MongoClient, db, GridFS
├── models/
│   └── user.py                # Flask-Login UserMixin with derived auth methods
├── scripts/
│   └── migrate_auth_schema.py # One-time migration for auth schema (already run)
└── tests/
    ├── conftest.py            # Shared fixtures, test user cleanup
    ├── test_auth_service.py   # Unit tests for auth business logic
    ├── test_auth_routes.py    # Integration tests for /auth/* endpoints
    └── test_user_routes.py    # Integration tests for user/profile/SSO endpoints
```

## API Reference

### Auth (`/auth/*`) — rate limited to 5 requests/minute

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/signup` | Create email/password account | No |
| POST | `/auth/login` | Log in with email/password | No |
| GET | `/auth/check` | Check if session is valid | No |
| POST | `/auth/logout` | End session | No |
| POST | `/auth/forgot-password` | Request password reset email | No |
| POST | `/auth/reset-password` | Reset password with token | No |
| POST | `/auth/change-password` | Change or set password | Yes |

### Users and Profiles

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/append_user_id` | Google SSO login/signup with identity resolution | No |
| GET | `/get_user_id` | Return current user's email | Yes |
| POST | `/save_profile` | Save profile data (education, subjects, hobbies) | Yes |
| POST | `/save_profile_picture` | Upload profile picture to GridFS | Yes |
| GET | `/get_user_profile` | Retrieve profile data, auth methods, personalization settings | Yes |

### AI (with hobby-based personalization)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/explain_text` | Detailed explanation of a quantum concept | No |
| POST | `/generate_analogy` | Everyday analogy for a quantum concept | No |
| POST | `/chat_about_text` | Conversational follow-up on highlighted text | No |
| POST | `/chat_quiz_question` | Contextual feedback on quiz answers | No |

### Quiz and Progress

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/save_quiz_result` | Save quiz score and unlock next levels | Yes |
| POST | `/save_first_lesson_view` | Mark first lesson as viewed | Yes |
| GET | `/get_user_progress` | Retrieve completed quizzes, unlocked levels, user info | Yes |

### Admin (requires admin session)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/upload_lesson` | Upload lesson metadata |
| POST | `/admin/upload_reading` | Upload reading media to GridFS |
| POST | `/admin/upload_quiz` | Upload quiz content |
| GET | `/admin/users` | List all users with metadata |
| POST | `/admin/users/<email>/disable` | Disable a user account |
| POST | `/admin/users/<email>/enable` | Re-enable a user account |
| GET | `/admin/feedback` | List feedback submissions |
| DELETE | `/admin/feedback/<id>` | Delete a feedback entry |

### Utility

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ping` | Health check (app + MongoDB connectivity) |
| GET | `/file/<id>` | Serve files from GridFS (profile pictures, screenshots) |

## License

MIT

## Citation

If referencing Quantaid in academic work:

> Kevin Hernandez, Tirthak Patel.
> *Enhancing Early Quantum Computing Education with QuantumAiEd: Bridging the Educational Gap.*
> SIGCSETS 2025: Proceedings of the 56th ACM Technical Symposium on Computer Science Education V. 2, p. 1755.
> [https://doi.org/10.1145/3641555.3705028](https://doi.org/10.1145/3641555.3705028)
> Published: February 18, 2025. ACM.
