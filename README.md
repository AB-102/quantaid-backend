# QuantumAiEdBackEnd

This is the backend for QuantumAiEd, an AI-powered tool for generating feedback on quantum computing content. It uses Python, Flask, and the OpenAI API.

## ⚙️ Tech Stack

- Python 3.8+
- Flask
- Flask-CORS
- OpenAI API

## 🚀 Setup Instructions

1. Clone the repository:

   git clone https://github.com/kevvinnnh/QuantumAiEdBackEnd.git
   cd QuantumAiEdBackEnd

2. Create and activate a virtual environment:

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install the dependencies:

   pip install -r requirements.txt

4. Set up environment variables:

   cp .env.example .env

   Then open `.env` and add:

   OPENAI_API_KEY=your_openai_api_key_here

5. Start the server:

   python app.py

   The backend will be available at http://localhost:5000

## 🧪 API Endpoints

- GET / — Health check
- POST /api/generate-feedback — Accepts input and returns AI-generated feedback

## ❗ Troubleshooting

- Make sure `.env` contains a valid OpenAI API key
- If CORS errors occur, ensure frontend is allowed in Flask-CORS config
- Use Postman to manually test the endpoints

## 📄 License

MIT
