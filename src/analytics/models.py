from django.db import models
from django.conf import settings
from src.properties.models import Property

class SearchQuery(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class ViewEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
