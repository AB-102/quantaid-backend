from flask import Blueprint, request, jsonify, session
from flask_cors import cross_origin
from flask_login import login_user, logout_user, current_user
from pymongo.errors import PyMongoError
from bson import ObjectId
from datetime import datetime, timezone
from config import FIRST_TIME_USER_EMAIL, ADMIN_EMAILS
from database.mongo import db, fs
from models.user import User
from services.auth_service import generate_login_id

users_bp = Blueprint('users', __name__)


@users_bp.route('/append_user_id', methods=['POST'])
@cross_origin(supports_credentials=True)
def append_user_id():
    """
    Google SSO login/signup endpoint.

    Identity resolution:
      1. Match by google_sub (returning Google user) — strongest match
      2. Match by email (implicit linking: email-signup user now using Google) — link account
      3. No match — create new user

    The frontend sends google_sub (the `sub` field from Google's userinfo),
    which is Google's immutable unique user ID.
    """
    try:
        data = request.json or {}
        email = data.get('user_id')
        name = data.get('name')
        picture = data.get('picture')
        google_sub = data.get('google_sub')  # Google's unique user ID
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        email = email.lower()
        is_admin = email in ADMIN_EMAILS

        # Force test email to always go through onboarding
        if email == FIRST_TIME_USER_EMAIL:
            user_doc = db.users.find_one({'user_id': email})
            if not user_doc:
                login_id = generate_login_id()
                user_doc = {
                    'user_id': email, 'name': name, 'picture': picture,
                    'google_sub': google_sub, 'password_hash': None,
                    'login_id': login_id, 'is_admin': is_admin,
                    'profile_complete': False, 'unlockedLevels': [0],
                    'completedQuizzes': [], 'hasViewedFirstLesson': False,
                    'createdAt': datetime.now(timezone.utc)
                }
                db.users.insert_one(user_doc)
            else:
                # Update google_sub if not set
                if google_sub and not user_doc.get('google_sub'):
                    db.users.update_one({'user_id': email}, {'$set': {'google_sub': google_sub}})
                    user_doc['google_sub'] = google_sub
            user = User(user_doc)
            login_user(user)
            session['login_id'] = user.login_id
            print(f"DEBUG: Test user {email} forced to onboarding.")
            return jsonify({'message': 'Test user - redirecting to onboarding', 'redirect_to': 'profile-creation', 'is_admin': is_admin}), 200

        # --- Identity resolution ---
        existing_user = None

        # 1. Try to match by google_sub (strongest: returning Google user)
        if google_sub:
            existing_user = db.users.find_one({'google_sub': google_sub})

        # 2. Fall back to email match (implicit linking or returning user without sub stored)
        if not existing_user:
            existing_user = db.users.find_one({'user_id': email})

        if existing_user:
            if existing_user.get('disabled', False):
                return jsonify({'error': 'This account has been disabled. Contact an administrator.'}), 403

            # Build update: rotate login_id, update admin flag, set lastLoginAt
            new_login_id = generate_login_id()
            update_fields = {
                'login_id': new_login_id,
                'is_admin': is_admin,
                'lastLoginAt': datetime.now(timezone.utc),
            }

            # Link Google if not already linked, or replace pending placeholder
            existing_sub = existing_user.get('google_sub') or ''
            if google_sub and (not existing_sub or existing_sub.startswith('pending:')):
                update_fields['google_sub'] = google_sub
                print(f"DEBUG: Linked Google account (sub={google_sub}) to existing user {email}")

            # Update Google profile picture if user doesn't have a custom GridFS one
            current_picture = existing_user.get('picture', '')
            if picture and not (current_picture and '/file/' in current_picture):
                update_fields['picture'] = picture

            # Update name if not set
            if name and not existing_user.get('name'):
                update_fields['name'] = name

            db.users.update_one(
                {'user_id': existing_user['user_id']},
                {'$set': update_fields}
            )
            existing_user['login_id'] = new_login_id
            existing_user['is_admin'] = is_admin
            if 'google_sub' in update_fields:
                existing_user['google_sub'] = update_fields['google_sub']
            user = User(existing_user)
            login_user(user)
            session['login_id'] = new_login_id

            print(f"DEBUG: User {email} logged in via Google SSO.")
            if existing_user.get('profile_complete'):
                return jsonify({'message': 'User exists and profile is complete', 'redirect_to': 'map', 'is_admin': is_admin}), 200
            else:
                return jsonify({'message': 'User exists but profile incomplete', 'redirect_to': 'profile-creation', 'is_admin': is_admin}), 200
        else:
            # 3. New user — create with Google SSO
            login_id = generate_login_id()
            new_user_data = {
                'user_id': email, 'name': name, 'picture': picture,
                'google_sub': google_sub, 'password_hash': None,
                'login_id': login_id, 'is_admin': is_admin,
                'profile_complete': False, 'unlockedLevels': [0],
                'completedQuizzes': [], 'hasViewedFirstLesson': False,
                'createdAt': datetime.now(timezone.utc)
            }
            db.users.insert_one(new_user_data)
            user = User(new_user_data)
            login_user(user)
            session['login_id'] = login_id

            print(f"DEBUG: New Google user {email} (sub={google_sub}) created and logged in.")
            return jsonify({'message': 'User data saved to MongoDB', 'redirect_to': 'profile-creation', 'is_admin': is_admin}), 201
    except PyMongoError as e:
        print(f"Error in /append_user_id (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error in /append_user_id: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500


@users_bp.route('/get_user_id', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_user_id():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User ID not found in session'}), 401
    return jsonify({'user_id': current_user.email}), 200


@users_bp.route('/save_profile', methods=['POST'])
@cross_origin(supports_credentials=True)
def save_profile():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User not logged in. Please log in again.'}), 401
    user_id = current_user.email
    try:
        data = request.json or {}
        print(f"DEBUG: Received data in /save_profile for user {user_id} =>", data)
        user_doc = db.users.find_one({'user_id': user_id})
        if not user_doc:
            logout_user()
            session.clear()
            return jsonify({'error': f"User not found with ID={user_id}. Please log in again."}), 404
        where_heard = data.get('whereHeard', [])
        other_where_heard = data.get('otherWhereHeard', '')
        education_category = data.get('educationCategory', '')
        education_level = data.get('educationLevel', '')
        other_education_level = data.get('otherEducationLevel', '')
        if education_category == 'HighSchool':
            final_education_level = f"High School - {education_level}"
        elif education_category == 'College':
            final_education_level = f"College - {education_level}"
        elif education_category == 'Other' and other_education_level:
            final_education_level = other_education_level
        else:
            final_education_level = ''
        subjects = data.get('subjects', [])
        other_subject = data.get('otherSubject', '')
        subjects_list = subjects.copy()
        if 'Other (please specify)' in subjects and other_subject:
            subjects_list = [s for s in subjects_list if s != 'Other (please specify)']
            subjects_list.append(other_subject)
        favorite_hobbies = data.get('favoriteHobbies', [])
        custom_hobbies = data.get('customHobbies', '').strip()
        all_hobbies = favorite_hobbies.copy()
        if custom_hobbies:
            custom_hobby_list = [h.strip() for h in custom_hobbies.split(',') if h.strip()]
            all_hobbies.extend(custom_hobby_list)
        if not isinstance(all_hobbies, list):
            all_hobbies = [str(all_hobbies)] if all_hobbies else []
        coding_experience = data.get('codingExperience', '')
        hobby_personalization = data.get('hobbyPersonalization', True)
        profile_data = {
            'where_heard': where_heard,
            'other_where_heard': other_where_heard,
            'education_category': education_category,
            'education_level': final_education_level,
            'subjects_studied': subjects_list,
            'other_subject': other_subject,
            'coding_experience': coding_experience,
            'favorite_hobbies': all_hobbies,
            'custom_hobbies': custom_hobbies,
        }
        print("DEBUG: Constructed profile_data =>", profile_data)
        update_result = db.users.update_one(
            {'user_id': user_id},
            {'$set': {
                'profile': profile_data, 'profile_complete': True,
                'hobby_personalization': hobby_personalization,
                'profileLastUpdatedAt': datetime.now(timezone.utc),
                'onboarding_responses': {
                    'where_heard': where_heard,
                    'other_where_heard': other_where_heard,
                    'education_category': education_category,
                    'subjects': subjects,
                    'other_subject': other_subject,
                    'favorite_hobbies': favorite_hobbies,
                    'custom_hobbies': custom_hobbies,
                    'coding_experience': coding_experience,
                    'completed_at': datetime.now(timezone.utc)
                }
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


@users_bp.route('/save_profile_picture', methods=['POST'])
@cross_origin(supports_credentials=True)
def save_profile_picture():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User not logged in'}), 401
    user_id = current_user.email
    try:
        if 'picture' not in request.files:
            return jsonify({'error': 'No picture file provided'}), 400
        picture_file = request.files['picture']
        if not picture_file.filename:
            return jsonify({'error': 'Empty filename'}), 400
        # Delete old GridFS picture if it exists
        user = db.users.find_one({'user_id': user_id}, {'picture': 1})
        old_picture = user.get('picture', '') if user else ''
        if old_picture and '/file/' in old_picture:
            try:
                old_id = old_picture.split('/file/')[-1]
                fs.delete(ObjectId(old_id))
            except Exception:
                pass  # Old file may not exist
        # Store new picture in GridFS
        picture_id = fs.put(
            picture_file,
            filename=picture_file.filename,
            content_type=picture_file.content_type or 'image/png',
            user_id=user_id
        )
        picture_url = f"/file/{str(picture_id)}"
        # Update user document
        db.users.update_one(
            {'user_id': user_id},
            {'$set': {'picture': picture_url}}
        )
        return jsonify({'url': picture_url}), 200
    except Exception as e:
        print(f"Error in /save_profile_picture: {e}")
        return jsonify({'error': 'Failed to save profile picture'}), 500


@users_bp.route('/get_user_profile', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_user_profile():
    if not current_user.is_authenticated:
        return jsonify({'error': 'User ID not found in session'}), 401
    user_id = current_user.email
    try:
        user = db.users.find_one(
            {'user_id': user_id},
            {'_id': 0, 'profile': 1, 'name': 1, 'picture': 1,
             'hobby_personalization': 1, 'password_hash': 1, 'google_sub': 1}
        )
        if not user:
            logout_user()
            session.clear()
            return jsonify({'error': 'User profile not found'}), 404
        profile = user.get('profile', {}) or {}
        response_data = {
            'name': user.get('name', 'User'),
            'profilePicture': user.get('picture', ''),
            'educationCategory': profile.get('education_category', ''),
            'educationLevel': profile.get('education_level', ''),
            'subjectsStudied': profile.get('subjects_studied', []),
            'codingExperience': profile.get('coding_experience', ''),
            'favoriteHobbies': profile.get('favorite_hobbies', []),
            'customHobbies': profile.get('custom_hobbies', ''),
            'hobbyPersonalization': user.get('hobby_personalization', True),
            'hasPassword': bool(user.get('password_hash')),
            'hasGoogle': bool(user.get('google_sub')),
        }
        return jsonify(response_data), 200
    except PyMongoError as e:
        print(f"Error in /get_user_profile (MongoDB): {e}")
        return jsonify({'error': f'Database error: {e}'}), 500
    except Exception as e:
        print(f"Error in /get_user_profile: {e}")
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500


