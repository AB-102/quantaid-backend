from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from datetime import datetime
from database.mongo import db, fs
from routes import admin_required

content_bp = Blueprint('content', __name__)


@content_bp.route('/admin/upload_lesson', methods=['POST', 'OPTIONS'])
@admin_required
@cross_origin(supports_credentials=True)
def upload_lesson():
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


@content_bp.route('/admin/upload_reading', methods=['POST', 'OPTIONS'])
@admin_required
def upload_reading():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        title = request.form.get('title')
        content = request.form.get('content')
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


@content_bp.route('/admin/upload_quiz', methods=['POST', 'OPTIONS'])
@admin_required
def upload_quiz():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json or {}
        quiz = {
            'questions': data.get('questions'),
            'created_at': datetime.utcnow()
        }
        db.quizzes.insert_one(quiz)
        return jsonify({'message': 'Quiz uploaded successfully'}), 200
    except Exception as e:
        print("Error uploading quiz:", e)
        return jsonify({'error': str(e)}), 500
