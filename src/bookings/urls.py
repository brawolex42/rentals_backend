
from django.urls import path
from .views import ConfirmCheckoutView, MarkOverdueView, CancelBookingView

urlpatterns = [
    path('<int:pk>/confirm-checkout/', ConfirmCheckoutView.as_view(), name='booking_confirm_checkout'),
    path('<int:pk>/mark-overdue/', MarkOverdueView.as_view(), name='booking_mark_overdue'),
    path('<int:pk>/cancel/', CancelBookingView.as_view(), name='booking_cancel'),
]
