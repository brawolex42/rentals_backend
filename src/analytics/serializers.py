from rest_framework import serializers
from .models import SearchQuery, ViewEvent

class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = '__all__'

class ViewEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewEvent
        fields = '__all__'
