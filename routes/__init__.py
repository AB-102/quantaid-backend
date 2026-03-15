from functools import wraps
from flask import request, make_response, jsonify
from flask_login import current_user


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.method == 'OPTIONS':
            return make_response(jsonify({'message': 'OK'}), 200)
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        return func(*args, **kwargs)
    return wrapper
