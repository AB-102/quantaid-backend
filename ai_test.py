from openai import OpenAI
from dotenv import load_dotenv

load_dotenv() 


client = OpenAI()

# Assuming `topic`, `hobby`, and `college_major` are pulled from your MongoDB
topic = "Quantum Computing in Cryptography"
hobby = "playing chess"
college_major = "Physics"

# Constructing the prompt to generate direct, self-contained questions
prompt = (f"Generate 10 high school-level multiple-choice questions about {topic}. "
          f"Each question should use an analogy related to {hobby} and {college_major} "
          "to explain a quantum concept in a relatable way. The Questions you generate should quiz a specific part of a quantum concpet (each question should test something specific about the concept). "
          "The questions you generate should focus on teaching quantum, not  asking 'Which analogy reflects this phenomenon?'."
          "The questions you generate should only be 1 sentence, and no more than 20 words."
          "Skip any introductions and go straight into the questions with 4 answer choices and the correct answer clearly indicated.")

completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant specialized in generating educational content."},
        {"role": "user", "content": prompt}
    ],
    n=1,  # Requesting one complete set of 10 questions and answers
    max_tokens=300  # Limiting the number of tokens for testing
)

# Extracting the generated content
questions_and_answers = completion.choices[0].message.content
print(questions_and_answers)


# client = OpenAI() 

# completion = client.chat.completions.create(
#     model="gpt-4o-mini",
#     messages=[
#         {"role": "system", "content": "You are a helpful assistant."},
#         {
#             "role": "user",
#             "content": "Write a haiku about recursion in programming."
#         }
#     ]
# )

# print(completion.choices[0].message.content)

# def generate_questions_for_topic(topic):
#     print(f"Calling OpenAI API for topic: {topic}")  # Log API call attempt
#     model="gpt-4o-mini",
#     messages = [
#         {"role": "system", "content": "You are an expert in quantum computing education."},
#         {
#             "role": "user",
#             "content": (
#                 f"Generate 10 diverse and thought-provoking graduate-level questions on the topic '{topic}'. "
#                 "The questions should cover conceptual understanding, practical applications, and recent developments in the field. "
#                 "Present the questions in a numbered list without providing the answers."
#             )
#         }
#     ]

#     try:
#         response = openai.ChatCompletion.create(
#             model="gpt-3.5-turbo",
#             messages=messages,
#             max_tokens=500,
#             temperature=0.7,
#         )
#         print("OpenAI API Response:", response)
#     except openai.error.OpenAIError as e:
#         print(f"OpenAI API error: {e}")
#         return []


#     # Ensure response has content before proceeding
#     if not response.choices or not response.choices[0].message:
#         print("OpenAI API returned an empty response or no choices.")
#         return []

#     questions_text = response.choices[0].message['content'].strip()

#     # Split and clean the questions
#     questions = []
#     for line in questions_text.split('\n'):
#         line = line.strip()
#         if line:
#             # Remove numbering if present
#             if line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
#                 line = line[2:].strip()
#             questions.append(line)

#     print("Parsed Questions:", questions)  # Log parsed questions to verify structure
#     return questions

# @app.route('/generate_questions', methods=['POST', 'OPTIONS'])
# def generate_questions():
#     if request.method == 'OPTIONS':
#         return '', 200

#     try:
#         # Fetch all chapters and their topics from the database
#         chapters = list(db.chapters.find({}))

#         for chapter in chapters:
#             chapter_number = chapter['chapter_number']
#             chapter_title = chapter['chapter_title']
#             for topic in chapter['topics']:
#                 # Check if questions for this topic already exist in the 'questions' collection
#                 existing = db.questions.find_one({'topic': topic})
#                 if existing:
#                     print(f"Questions for topic '{topic}' already exist. Skipping.")
#                     continue

#                 # Generate questions for the topic
#                 questions = generate_questions_for_topic(topic)
#                 if not questions:
#                     print(f"No questions generated for topic '{topic}'. Skipping insertion.")
#                     continue  # Skip if no questions were generated

#                 # Attempt to store the questions in the 'questions' collection
#                 # Test insertion
#                 try:
#  # Insert the actual questions
#                     db.questions.insert_one({
#                         'topic': topic,
#                         'chapter_number': chapter_number,
#                         'chapter_title': chapter_title,
#                         'questions': questions
#                     })

#                     print("Test document inserted successfully.")
#                 except Exception as test_insert_error:
#                     print("Test insertion failed:", test_insert_error)


#         return jsonify({'message': 'Questions generation attempt complete'}), 200

#     except Exception as e:
#         print('Error occurred in question generation:', str(e))
#         return jsonify({'error': str(e)}), 500
