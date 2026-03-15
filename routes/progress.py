from flask import Blueprint, request, jsonify, session
from flask_cors import cross_origin
from flask_login import current_user, logout_user
from pymongo.errors import PyMongoError
from datetime import datetime, timezone
from config import FIRST_TIME_USER_EMAIL
from database.mongo import db

progress_bp = Blueprint('progress', __name__)


@progress_bp.route('/save_quiz_result', methods=['POST'])
@cross_origin(supports_credentials=True)
def save_quiz_result():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User not logged in'}), 401
    user_id = current_user.email
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


@progress_bp.route('/save_first_lesson_view', methods=['POST'])
@cross_origin(supports_credentials=True)
def save_first_lesson_view():
    """Save that user has viewed their first lesson"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'User not logged in'}), 401
    user_id = current_user.email

    # Skip saving for test email
    if user_id == FIRST_TIME_USER_EMAIL:
        print(f"DEBUG: Skipping first lesson save for test user {user_id}")
        return jsonify({'message': 'Test user - onboarding state not saved'}), 200

    try:
        update_result = db.users.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'hasViewedFirstLesson': True,
                    'firstLessonViewedAt': datetime.now(timezone.utc)
                }
            }
        )

        if update_result.matched_count == 0:
            return jsonify({'error': 'User not found'}), 404

        print(f"DEBUG: First lesson view saved for user {user_id}")
        return jsonify({'message': 'First lesson view saved successfully'}), 200

    except PyMongoError as e:
        print(f"Error saving first lesson view (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error saving first lesson view: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500


@progress_bp.route('/get_user_progress', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_user_progress():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User not logged in'}), 401
    user_id = current_user.email
    try:
        user = db.users.find_one(
            {'user_id': user_id},
            {
                '_id': 0,
                'unlockedLevels': 1,
                'completedQuizzes': 1,
                'hasViewedFirstLesson': 1,
                'name': 1,
                'picture': 1
            }
        )
        if not user:
            logout_user()
            session.clear()
            return jsonify({'error': 'User data not found for this session'}), 404
        unlocked_levels = user.get('unlockedLevels', [0])
        completed_quizzes = user.get('completedQuizzes', [])
        has_viewed_first_lesson = user.get('hasViewedFirstLesson', False)
        # Force test email to always show onboarding
        if user_id == FIRST_TIME_USER_EMAIL:
            has_viewed_first_lesson = False
            print(f"DEBUG: Test user {user_id} - forcing hasViewedFirstLesson to False")
        print(f"DEBUG: Fetched progress for user {user_id}: Unlocked {unlocked_levels}")
        return jsonify({
            'unlockedLevels': unlocked_levels,
            'completedQuizzes': completed_quizzes,
            'hasViewedFirstLesson': has_viewed_first_lesson,
            'email': user_id,
            'name': user.get('name', ''),
            'picture': user.get('picture', '')
            }), 200
    except PyMongoError as e:
        print(f"Error fetching user progress (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error fetching user progress: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500
