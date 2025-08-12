from rest_framework.permissions import BasePermission

class IsBookingOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.tenant_id == getattr(request.user, 'id', None)
