from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, ContactPropertyView

router = DefaultRouter()
router.register('', PropertyViewSet, basename='property')

urlpatterns = [
    path('<int:pk>/contact/', ContactPropertyView.as_view(), name='property_contact'),
]

urlpatterns += router.urls
