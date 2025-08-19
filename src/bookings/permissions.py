
from rest_framework.permissions import BasePermission

class IsBookingOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        return obj.tenant_id == getattr(user, 'id', None)

class IsBookingOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        return obj.tenant_id == getattr(user, 'id', None) or getattr(user, 'is_staff', False)
