# pyrefly: ignore [missing-import]
from django.contrib.auth.backends import ModelBackend
# pyrefly: ignore [missing-import]
from django.contrib.auth import get_user_model


User = get_user_model()


def _normalize_phone_number(value):
    value = (value or "").strip()
    if not value:
        return ""
    normalized = value.replace(" ", "").replace("-", "")
    return normalized


class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("email") or kwargs.get("phone_number")
        if not identifier or password is None:
            return None

        identifier = str(identifier).strip()
        if not identifier:
            return None

        user = User.objects.filter(email__iexact=identifier).first()
        if user is None:
            normalized_phone = _normalize_phone_number(identifier)
            candidates = {normalized_phone}
            if normalized_phone.startswith("+"):
                candidates.add(normalized_phone.lstrip("+"))
            elif normalized_phone:
                candidates.add(f"+{normalized_phone}")
            user = User.objects.filter(phone_number__in=[candidate for candidate in candidates if candidate]).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
