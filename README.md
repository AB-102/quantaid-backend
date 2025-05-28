# QuantumAiEdBackEnd

This is the backend for QuantumAiEd, an AI-powered tool for generating feedback on quantum computing content. It uses Python, Flask, MongoDB, and the OpenAI API.

## ⚙️ Tech Stack

- Python 3.8+
- Flask
- Flask-CORS
- MongoDB
- OpenAI API

## 🚀 Setup Instructions

1. Clone the repository:

   git clone https://github.com/kevvinnnh/QuantumAiEdBackEnd.git
   cd QuantumAiEdBackEnd

2. Create and activate a virtual environment:

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:

   pip install -r requirements.txt

4. Set up environment variables:

   cp .env.example .env

   Open `.env` and fill in:

   FLASK_SECRET_KEY=your_secret_key_here  
   OPENAI_API_KEY=your_openai_api_key_here  
   MONGODB_URI=your_mongodb_connection_uri  
   SESSION_COOKIE_SECURE=False  
   CORS_ORIGIN=http://localhost:5173

5. Run the backend server:

   python app.py

   Server will be available at http://localhost:5000

## 🧪 API Endpoints

- GET / — Health check
- POST /api/generate-feedback — Accepts input and returns AI-generated feedback

## ❗ Troubleshooting

- Make sure `.env` has all required variables
- Ensure MongoDB is running or remote connection string is valid
- If CORS errors occur, check that `CORS_ORIGIN` matches your frontend address
- Test using Postman to verify endpoint responses

## 📄 License

MIT
