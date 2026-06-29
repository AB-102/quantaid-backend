from typing import cast

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from flask_login import current_user
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from config import CORS_ORIGINS, OPENAI_API_KEY
from database.mongo import db

ai_bp = Blueprint("ai", __name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)


def _get_personalization_context() -> str:
    """
    Build a personalization string from the user's hobbies/interests,
    if the user is logged in and has hobby personalization enabled.
    Returns an empty string if personalization is off or no hobbies set.
    """
    if not current_user.is_authenticated:
        return ""
    user_doc = db.users.find_one({"user_id": current_user.email}, {"_id": 0, "profile": 1, "hobby_personalization": 1})
    if not user_doc:
        return ""
    # Check if personalization is enabled (defaults to True for new users)
    if not user_doc.get("hobby_personalization", True):
        return ""
    profile = user_doc.get("profile") or {}
    hobbies = profile.get("favorite_hobbies", [])
    if not hobbies:
        return ""
    hobby_str = ", ".join(hobbies[:8])  # Cap at 8 to keep prompt short
    return (
        f"\nThe student's interests include: {hobby_str}. "
        "When possible, relate quantum concepts to these interests using analogies they'd find relatable. "
        "Don't force it — only use hobby-based analogies when they genuinely help explain the concept."
    )


@ai_bp.route("/explain_text", methods=["POST", "OPTIONS"])
@cross_origin(origins=CORS_ORIGINS, supports_credentials=True)
def explain_text():
    try:
        data = request.json or {}
        text = data.get("text")
        if not text:
            return jsonify({"error": "No text provided"}), 400

        personalization = _get_personalization_context()

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
                "- Be engaging and encouraging" + personalization
            ),
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
            ),
        }
        messages = cast(list[ChatCompletionMessageParam], [system_prompt, user_msg])
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=250, temperature=0.6
        )
        explanation = (response.choices[0].message.content or "").strip()
        return jsonify({"explanation": explanation}), 200
    except Exception as e:
        print("Error in /explain_text:", e)
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/chat_about_text", methods=["POST", "OPTIONS"])
@cross_origin(origins=CORS_ORIGINS, supports_credentials=True)
def chat_about_text():
    try:
        data = request.json or {}
        highlighted_text = data.get("highlighted_text", "")
        conversation_history = data.get("messages", [])
        if not highlighted_text:
            highlighted_text = "(No specific highlighted text, user wants a general chat.)"

        personalization = _get_personalization_context()

        system_prompt = {
            "role": "system",
            "content": (
                "You are a concise quantum tutor. Use bullet points, ask if the student understands, "
                "and provide an extra example at the end." + personalization
            ),
        }
        user_msg = {"role": "user", "content": f"Discuss the highlighted text: '{highlighted_text}'."}
        messages = cast(list[ChatCompletionMessageParam], [system_prompt, user_msg] + conversation_history)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=300, temperature=0.6
        )
        bot_reply = (response.choices[0].message.content or "").strip()
        return jsonify({"assistant_reply": bot_reply}), 200
    except Exception as e:
        print("Error in /chat_about_text:", e)
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/chat_quiz_question", methods=["POST", "OPTIONS"])
@cross_origin(origins=CORS_ORIGINS, supports_credentials=True)
def chat_quiz_question():
    try:
        data = request.json or {}
        question_text = data.get("question_text", "")
        conversation_history = data.get("messages", [])
        is_correct = data.get("isCorrect", None)
        selected_answer = data.get("selectedAnswer", "")
        correct_answer = data.get("correctAnswer", "")

        if not question_text:
            return jsonify({"error": "No question_text provided"}), 400

        personalization = _get_personalization_context()

        system_instructions = "You are a helpful quantum tutor. Use bullet points and clear language. "
        if is_correct is True:
            system_instructions += (
                f'The student answered correctly. Their answer was: "{selected_answer}" '
                f'which is correct because "{correct_answer}". '
                "Provide a detailed explanation reinforcing why that answer is correct and highlighting key concepts."
            )
        elif is_correct is False:
            system_instructions += (
                f'The student answered incorrectly. Their answer was: "{selected_answer}" '
                f'but the correct answer is: "{correct_answer}". '
                "Explain common misconceptions and clearly detail why the correct answer is right."
            )
        else:
            system_instructions += "Provide a concise explanation of the question."

        system_instructions += personalization

        system_prompt = {
            "role": "system",
            "content": system_instructions,
        }
        user_msg = {"role": "user", "content": f"Help me understand this quiz question:\n{question_text}"}
        messages = cast(list[ChatCompletionMessageParam], [system_prompt, user_msg] + conversation_history)

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=350, temperature=0.6
        )
        bot_reply = (response.choices[0].message.content or "").strip()
        return jsonify({"assistant_reply": bot_reply}), 200
    except Exception as e:
        print("Error in /chat_quiz_question:", e)
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/generate_analogy", methods=["POST", "OPTIONS"])
@cross_origin(origins=CORS_ORIGINS, supports_credentials=True)
def generate_analogy():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "No text provided for analogy"}), 400

        personalization = _get_personalization_context()

        system_prompt = {
            "role": "system",
            "content": (
                "Create clear, relatable analogies for quantum computing concepts using everyday objects. "
                "Keep responses 200-250 words. Use simple language and direct comparisons. "
                "Structure: introduce analogy, explain the parallel, connect back to quantum concept." + personalization
            ),
        }
        user_prompt = {
            "role": "user",
            "content": (
                f"Create a clear analogy for this quantum concept using an everyday scenario:\n\n"
                f'"{text}"\n\n'
                f"Use simple language and explain how the analogy relates to the quantum concept. "
                f"Keep it engaging but concise."
            ),
        }
        messages = cast(list[ChatCompletionMessageParam], [system_prompt, user_prompt])

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=messages, max_tokens=250, temperature=0.7
        )
        analogy = (response.choices[0].message.content or "").strip()
        return jsonify({"analogy": analogy}), 200
    except Exception as e:
        print("Error in /generate_analogy:", e)
        return jsonify({"error": str(e)}), 500
