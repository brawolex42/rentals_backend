from rest_framework import serializers
from django.apps import apps


def _get_model(name: str):
    try:
        return apps.get_model(apps.get_app_config("analytics").label, name)
    except Exception:
        return None


SearchQuery = _get_model("SearchQuery")
ViewEvent = _get_model("ViewEvent")


if SearchQuery:
    class SearchQuerySerializer(serializers.ModelSerializer):
        class Meta:
            model = SearchQuery
            fields = "__all__"
else:
    class SearchQuerySerializer(serializers.Serializer):
        id = serializers.IntegerField(read_only=True)
        query = serializers.CharField(required=False, allow_blank=True)
        created_at = serializers.DateTimeField(required=False)


if ViewEvent:
    class ViewEventSerializer(serializers.ModelSerializer):
        class Meta:
            model = ViewEvent
            fields = "__all__"
else:
    class ViewEventSerializer(serializers.Serializer):
        id = serializers.IntegerField(read_only=True)
        path = serializers.CharField(required=False, allow_blank=True)
        created_at = serializers.DateTimeField(required=False)
