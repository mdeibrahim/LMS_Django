from rest_framework.permissions import BasePermission

from .models import UserRole
from .services import ensure_profile


class IsStudent(BasePermission):
    message = 'Student role required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile = ensure_profile(request.user)
        return profile.role == UserRole.STUDENT
