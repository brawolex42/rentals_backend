from django.urls import path
from .views import PopularSearchesView, MySearchHistoryView, MyViewHistoryView

urlpatterns = [
    path("", PopularSearchesView.as_view(), name="popular-searches"),                 # /api/analytics/
    path("popular-searches/", PopularSearchesView.as_view(), name="popular-searches-dup"),
    path("my-searches/", MySearchHistoryView.as_view(), name="my-searches"),
    path("my-views/", MyViewHistoryView.as_view(), name="my-views"),
]
