#schemas.py

from mongoengine import Document, StringField, ListField, IntField, ObjectIdField, DateTimeField, DictField

class User(Document):
    user_id = ObjectIdField(required=True)  # Unique identifier for the user
    email = StringField(required=True)  # User's email

class UserSession(Document):
    user_id = ObjectIdField(required=True)  # Reference to the user
    session_token = StringField(required=True)  # Unique session token
    created_at = DateTimeField(required=True)  # Timestamp for when the session was created
    expires_at = DateTimeField(required=True)  # Timestamp for when the session expires

# Additional classes can be added as needed for your application