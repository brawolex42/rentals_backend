from django.db.models import Count
from rest_framework import generics, permissions
from .models import SearchQuery, ViewEvent
from .serializers import SearchQuerySerializer, ViewEventSerializer
from src.properties.models import Property
from rest_framework.response import Response
from rest_framework.views import APIView

class PopularSearchesView(generics.ListAPIView):
    """
    ТОП ключевых слов (агрегировано).
    """
    serializer_class = SearchQuerySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return (
            SearchQuery.objects
            .values('query')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')[:50]
        )

class MySearchHistoryView(generics.ListAPIView):
    """
    Моя история поисков (последние 100).
    """
    serializer_class = SearchQuerySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SearchQuery.objects.filter(user=self.request.user).order_by('-created_at')[:100]

class MyViewHistoryView(generics.ListAPIView):
    """
    Мои просмотры объявлений (последние 200).
    """
    serializer_class = ViewEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ViewEvent.objects.select_related('property').filter(user=self.request.user).order_by('-created_at')[:200]
