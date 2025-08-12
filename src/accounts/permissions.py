from rest_framework.permissions import BasePermission
from src.shared.enums import UserRole

class IsLandlord(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.LANDLORD)

class IsTenant(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.TENANT)
