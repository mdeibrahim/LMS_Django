from pathlib import Path

from django.conf import settings


try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials
except Exception:  # pragma: no cover - optional dependency
    firebase_admin = None
    firebase_auth = None
    credentials = None


def initialize_firebase():
    if firebase_admin is None or credentials is None:
        return False

    if firebase_admin._apps:
        return True

    service_account_file = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_FILE", "")
    if not service_account_file:
        return False

    path = Path(service_account_file)
    if not path.exists():
        return False

    cred = credentials.Certificate(str(path))
    firebase_admin.initialize_app(cred)
    return True


def verify_id_token(id_token):
    if firebase_auth is None:
        raise RuntimeError("firebase_admin is not installed")

    initialize_firebase()
    return firebase_auth.verify_id_token(id_token)
