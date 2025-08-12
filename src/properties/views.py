from django.db.models import F
from rest_framework import viewsets, decorators, response, status, permissions
from .models import Property
from .serializers import PropertySerializer
from .filters import PropertyFilter
from .permissions import IsOwnerOrReadOnly
from src.accounts.permissions import IsLandlord
from src.analytics.models import ViewEvent

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all().select_related('owner')
    serializer_class = PropertySerializer
    filterset_class = PropertyFilter
    search_fields = ('title', 'description')
    ordering_fields = ('price', 'created_at', 'views_count', 'reviews_count')
    ordering = ('-created_at',)

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsLandlord()]
        elif self.action in ['update', 'partial_update', 'destroy', 'toggle_active']:
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # инкремент просмотров (атомарно)
        Property.objects.filter(pk=obj.pk).update(views_count=F('views_count') + 1)
        # пишем событие просмотра
        user = request.user if request.user.is_authenticated else None
        ViewEvent.objects.create(user=user, property=obj)
        serializer = self.get_serializer(obj)
        return response.Response(serializer.data)

    @decorators.action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        prop = self.get_object()
        prop.is_active = not prop.is_active
        prop.save(update_fields=['is_active'])
        return response.Response({'is_active': prop.is_active})

    @decorators.action(detail=False, methods=['get'])
    def popular(self, request):
        by = request.query_params.get('by', 'views')
        if by == 'reviews':
            qs = self.filter_queryset(self.get_queryset().order_by('-reviews_count', '-views_count', '-created_at'))
        else:
            qs = self.filter_queryset(self.get_queryset().order_by('-views_count', '-reviews_count', '-created_at'))
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return response.Response(ser.data)
