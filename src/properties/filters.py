import django_filters as filters
from .models import Property

class PropertyFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')
    city = filters.CharFilter(field_name='city', lookup_expr='iexact')
    district = filters.CharFilter(field_name='district', lookup_expr='iexact')
    min_rooms = filters.NumberFilter(field_name='rooms', lookup_expr='gte')
    max_rooms = filters.NumberFilter(field_name='rooms', lookup_expr='lte')
    property_type = filters.CharFilter(field_name='property_type', lookup_expr='iexact')
    is_active = filters.BooleanFilter()

    class Meta:
        model = Property
        fields = []
