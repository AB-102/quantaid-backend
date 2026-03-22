from flask import Blueprint, request, jsonify, Response
from flask_cors import cross_origin
from flask_login import current_user
from pymongo.errors import PyMongoError
from bson import ObjectId
from datetime import datetime, timezone
import csv
import io
from database.mongo import db, fs
from routes import admin_required

feedback_bp = Blueprint('feedback', __name__)


@feedback_bp.route('/submit_feedback', methods=['POST'])
@cross_origin(supports_credentials=True)
def submit_feedback():
    """
    Handle feedback submissions from the frontend.
    Accepts both JSON data and form data (for file uploads).
    """
    try:
        user_id = current_user.email if current_user.is_authenticated else 'anonymous'

        if request.content_type and 'multipart/form-data' in request.content_type:
            category = request.form.get('category', '')
            feedback_text = request.form.get('feedback', '')

            screenshot_id = None
            if 'screenshot' in request.files:
                screenshot_file = request.files['screenshot']
                if screenshot_file and screenshot_file.filename:
                    screenshot_id = fs.put(
                        screenshot_file,
                        filename=screenshot_file.filename,
                        content_type=screenshot_file.content_type,
                        visibility='admin'
                    )
        else:
            data = request.json or {}
            category = data.get('category', '')
            feedback_text = data.get('feedback', '')
            screenshot_id = None

        if not category or not feedback_text.strip():
            return jsonify({'error': 'Category and feedback text are required'}), 400

        feedback_doc = {
            'user_id': user_id,
            'category': category,
            'feedback': feedback_text.strip(),
            'screenshot_id': screenshot_id,
            'status': 'open',
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }

        result = db.feedback.insert_one(feedback_doc)

        print(f"DEBUG: Feedback submitted by user {user_id}, category: {category}")

        return jsonify({
            'message': 'Feedback submitted successfully',
            'feedback_id': str(result.inserted_id)
        }), 200

    except PyMongoError as e:
        print(f"Error saving feedback (MongoDB): {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        print(f"Error in /submit_feedback: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@feedback_bp.route('/feedback_file/<file_id>', methods=['GET'])
@admin_required
def get_feedback_file(file_id):
    """
    Retrieve uploaded feedback files (screenshots) by ID.
    Only accessible to admin users.
    """
    try:
        file_obj = fs.get(ObjectId(file_id))

        return Response(
            file_obj.read(),
            mimetype=file_obj.content_type or 'application/octet-stream',
            headers={
                'Content-Disposition': f'inline; filename="{file_obj.filename}"'
            }
        )
    except Exception as e:
        print(f"Error retrieving feedback file {file_id}: {e}")
        return jsonify({'error': 'File not found'}), 404


@feedback_bp.route('/admin/feedback', methods=['GET'])
@admin_required
@cross_origin(supports_credentials=True)
def get_all_feedback():
    """Get all feedback submissions for admin review."""
    try:
        status = request.args.get('status', None)
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        query = {}
        if status:
            query['status'] = status

        feedback_list = list(
            db.feedback.find(query, {'_id': 1, 'user_id': 1, 'category': 1,
                                   'feedback': 1, 'status': 1, 'created_at': 1,
                                   'screenshot_id': 1})
            .sort('created_at', -1)
            .skip(skip)
            .limit(limit)
        )

        for feedback in feedback_list:
            feedback['_id'] = str(feedback['_id'])
            if feedback.get('screenshot_id'):
                feedback['screenshot_id'] = str(feedback['screenshot_id'])
                feedback['has_screenshot'] = True
            else:
                feedback['has_screenshot'] = False

        total_count = db.feedback.count_documents(query)

        return jsonify({
            'feedback': feedback_list,
            'total_count': total_count,
            'has_more': (skip + len(feedback_list)) < total_count
        }), 200

    except Exception as e:
        print(f"Error fetching feedback: {e}")
        return jsonify({'error': str(e)}), 500


@feedback_bp.route('/admin/feedback/export', methods=['GET'])
@admin_required
@cross_origin(supports_credentials=True)
def export_feedback_csv():
    """Export all feedback as a CSV file download."""
    try:
        status = request.args.get('status', None)
        query = {}
        if status:
            query['status'] = status

        feedback_list = list(
            db.feedback.find(query, {
                'user_id': 1, 'category': 1, 'feedback': 1,
                'status': 1, 'created_at': 1, 'screenshot_id': 1
            }).sort('created_at', -1)
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'User', 'Category', 'Status', 'Feedback', 'Screenshot URL'])

        for fb in feedback_list:
            created = fb.get('created_at', '')
            if isinstance(created, datetime):
                created = created.strftime('%Y-%m-%d %H:%M:%S UTC')
            screenshot_url = ''
            if fb.get('screenshot_id'):
                screenshot_url = f"{request.host_url}feedback_file/{fb['screenshot_id']}"
            writer.writerow([
                created,
                fb.get('user_id', 'anonymous'),
                fb.get('category', ''),
                fb.get('status', 'open'),
                fb.get('feedback', ''),
                screenshot_url
            ])

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=feedback_export.csv'}
        )

    except Exception as e:
        print(f"Error exporting feedback: {e}")
        return jsonify({'error': str(e)}), 500


@feedback_bp.route('/admin/feedback/<feedback_id>/status', methods=['PATCH'])
@admin_required
@cross_origin(supports_credentials=True)
def update_feedback_status(feedback_id):
    """Update the status of a feedback submission."""
    try:
        data = request.json or {}
        new_status = data.get('status', '')

        if new_status not in ('open', 'in_progress', 'resolved'):
            return jsonify({'error': 'Invalid status. Must be open, in_progress, or resolved.'}), 400

        result = db.feedback.update_one(
            {'_id': ObjectId(feedback_id)},
            {'$set': {'status': new_status, 'updated_at': datetime.now(timezone.utc)}}
        )

        if result.matched_count == 0:
            return jsonify({'error': 'Feedback not found'}), 404

        return jsonify({'message': 'Status updated', 'status': new_status}), 200

    except Exception as e:
        print(f"Error updating feedback status: {e}")
        return jsonify({'error': str(e)}), 500


@feedback_bp.route('/admin/feedback/<feedback_id>', methods=['DELETE'])
@admin_required
@cross_origin(supports_credentials=True)
def delete_feedback(feedback_id):
    """Delete a feedback submission and its associated screenshot."""
    try:
        feedback = db.feedback.find_one({'_id': ObjectId(feedback_id)})
        if not feedback:
            return jsonify({'error': 'Feedback not found'}), 404

        if feedback.get('screenshot_id'):
            try:
                fs.delete(feedback['screenshot_id'])
            except Exception as e:
                print(f"Warning: Could not delete screenshot {feedback['screenshot_id']}: {e}")

        db.feedback.delete_one({'_id': ObjectId(feedback_id)})
        return jsonify({'message': 'Feedback deleted successfully'}), 200

    except Exception as e:
        print(f"Error deleting feedback: {e}")
        return jsonify({'error': str(e)}), 500
