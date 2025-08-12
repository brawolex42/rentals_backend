from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('src.accounts.urls')),
    path('api/', include('src.properties.urls')),
    path('api/', include('src.bookings.urls')),
    path('api/', include('src.reviews.urls')),
    path('api/analytics/', include('src.analytics.urls')),
]
