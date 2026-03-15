from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from datetime import datetime, timezone
from database.mongo import db
from routes import admin_required

admin_users_bp = Blueprint('admin_users', __name__)


@admin_users_bp.route('/admin/users', methods=['GET'])
@admin_required
@cross_origin(supports_credentials=True)
def get_all_users():
    """Get all users with metadata for admin review."""
    try:
        search = request.args.get('search', '').strip().lower()
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        query = {}
        if search:
            query['$or'] = [
                {'user_id': {'$regex': search, '$options': 'i'}},
                {'name': {'$regex': search, '$options': 'i'}},
            ]

        users = list(
            db.users.find(query, {
                '_id': 0,
                'user_id': 1,
                'name': 1,
                'google_sub': 1,
                'password_hash': 1,
                'is_admin': 1,
                'profile_complete': 1,
                'disabled': 1,
                'createdAt': 1,
                'lastLoginAt': 1,
            })
            .sort('createdAt', -1)
            .skip(skip)
            .limit(limit)
        )

        total_count = db.users.count_documents(query)
        total_users = db.users.count_documents({})

        # Serialize and derive auth methods
        for user in users:
            # Derive auth_methods from populated fields
            methods = []
            if user.get('google_sub'):
                methods.append('google')
            if user.get('password_hash'):
                methods.append('email')
            user['auth_methods'] = methods

            # Remove sensitive/internal fields from response
            user.pop('google_sub', None)
            user.pop('password_hash', None)

            for field in ('createdAt', 'lastLoginAt'):
                val = user.get(field)
                if isinstance(val, datetime):
                    user[field] = val.isoformat()
                elif val is None:
                    user[field] = None

        return jsonify({
            'users': users,
            'total_count': total_count,
            'total_users': total_users,
            'has_more': (skip + len(users)) < total_count,
        }), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500


@admin_users_bp.route('/admin/users/<path:email>/disable', methods=['PATCH'])
@admin_required
@cross_origin(supports_credentials=True)
def toggle_disable_user(email):
    """Toggle the disabled state of a user account."""
    try:
        user = db.users.find_one({'user_id': email}, {'disabled': 1})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        new_state = not user.get('disabled', False)
        db.users.update_one(
            {'user_id': email},
            {'$set': {
                'disabled': new_state,
                'disabledAt': datetime.now(timezone.utc) if new_state else None,
            }}
        )

        return jsonify({
            'message': f"User {'disabled' if new_state else 'enabled'}",
            'disabled': new_state,
        }), 200

    except Exception as e:
        print(f"Error toggling user disable: {e}")
        return jsonify({'error': str(e)}), 500
