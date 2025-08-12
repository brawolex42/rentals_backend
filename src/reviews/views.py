from django.db.models import F
from rest_framework import viewsets, permissions
from .models import Review
from .serializers import ReviewSerializer
from src.properties.models import Property

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related('property', 'author')
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        review = serializer.save(author=self.request.user)
        Property.objects.filter(pk=review.property_id).update(reviews_count=F('reviews_count') + 1)
