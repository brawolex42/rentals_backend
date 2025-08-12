from django.utils import timezone
from rest_framework import viewsets, decorators, response, status, permissions
from .models import Booking
from .serializers import BookingSerializer
from .permissions import IsBookingOwner
from src.accounts.permissions import IsTenant, IsLandlord
from src.shared.enums import BookingStatus

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related('property', 'tenant', 'property__owner')
    serializer_class = BookingSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsTenant()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsBookingOwner()]
        elif self.action in ['approve', 'decline']:
            return [permissions.IsAuthenticated(), IsLandlord()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user, status=BookingStatus.PENDING)

    @decorators.action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        # отмена разрешена только до даты начала
        today = timezone.localdate()
        if booking.tenant_id != request.user.id:
            return response.Response(status=status.HTTP_403_FORBIDDEN)
        if today >= booking.start_date:
            return response.Response({"detail": "Отменить можно только до даты начала."},
                                     status=status.HTTP_400_BAD_REQUEST)
        booking.status = BookingStatus.CANCELED
        booking.save(update_fields=['status'])
        return response.Response({'status': booking.status})

    @decorators.action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        booking = self.get_object()
        if booking.property.owner_id != request.user.id:
            return response.Response(status=status.HTTP_403_FORBIDDEN)
        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=['status'])
        return response.Response({'status': booking.status})

    @decorators.action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        booking = self.get_object()
        if booking.property.owner_id != request.user.id:
            return response.Response(status=status.HTTP_403_FORBIDDEN)
        booking.status = BookingStatus.DECLINED
        booking.save(update_fields=['status'])
        return response.Response({'status': booking.status})
