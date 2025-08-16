from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from src.properties.views import PublicCatalogView, PublicPropertyDetailView
from src.bookings.views import book_now
from src.reviews.views import submit_review
from django.conf import settings
from django.conf.urls.static import static
from src.bookings.views import MyBookingsView, EditBookingView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', PublicCatalogView.as_view(), name='home'),
    path('properties/<int:pk>/', PublicPropertyDetailView.as_view(), name='property_detail'),
    path('properties/<int:pk>/book-now/', book_now, name='property_book_now'),
    path('properties/<int:pk>/review/', submit_review, name='property_add_review'),
    path('register/', TemplateView.as_view(template_name="users/register.html"), name='register_page'),
    path('my/bookings/', MyBookingsView.as_view(), name='my_bookings'),
    path('my/bookings/<int:pk>/edit/', EditBookingView.as_view(), name='booking_edit'),
    path('api/accounts/', include('src.accounts.urls')),
    path('api/properties/', include('src.properties.urls')),
    path('api/bookings/', include('src.bookings.urls')),
    path('api/reviews/', include('src.reviews.urls')),
    path('api/analytics/', include('src.analytics.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
