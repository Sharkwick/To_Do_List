import os, json
import firebase_admin
from firebase_admin import credentials, firestore

def load_firebase_credentials():
    try:
        return credentials.Certificate("secrets/serviceAccountKey.json")
    except FileNotFoundError:
        raw = os.getenv("FIREBASE_KEY_JSON")
        if not raw:
            raise ValueError("Firebase credentials not found.")
        return credentials.Certificate(json.loads(raw))

def initialize_firebase():
    if not firebase_admin._apps:
        cred = load_firebase_credentials()
        firebase_admin.initialize_app(cred)
    return firestore.client()