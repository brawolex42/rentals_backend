# # rentals_backend/urls.py
# from django.contrib import admin
# from django.urls import path, include
# from django.conf import settings
# from django.conf.urls.static import static
# from django.conf.urls.i18n import i18n_patterns
#
# from src.properties.views import PublicCatalogView, PublicPropertyDetailView
# from src.reviews.views import submit_review
# import src.bookings.views as booking_views
# from src.accounts import views_html as account_views
# from src.shared.views import setlang_get
#
# urlpatterns = [
#     path("i18n/", include("django.conf.urls.i18n")),
#     path("lang/", setlang_get, name="setlang_get"),
#
#     path("api/accounts/", include("src.accounts.urls")),
#     path("api/properties/", include("src.properties.urls")),
#     path("api/bookings/", include("src.bookings.urls")),
#     path("api/reviews/", include("src.reviews.urls")),
#     path("api/analytics/", include("src.analytics.urls")),
# ]
#
# urlpatterns += i18n_patterns(
#     path("admin/", admin.site.urls),
#
#     path("", PublicCatalogView.as_view(), name="home"),
#     path("properties/<int:pk>/", PublicPropertyDetailView.as_view(), name="property_detail"),
#     path("properties/<int:pk>/book-now/", booking_views.book_now, name="property_book_now"),
#     path("properties/<int:pk>/review/", submit_review, name="property_add_review"),
#
#     path("register/", account_views.register_html, name="register_page"),
#     path("login/", account_views.login_html, name="login_page"),
#     path("logout/", account_views.logout, name="logout"),
#
#     path("my/bookings/", booking_views.MyBookingsView.as_view(), name="my_bookings"),
#     path("my/bookings/<int:pk>/edit/", booking_views.EditBookingView.as_view(), name="booking_edit"),
#     path("my/bookings/<int:pk>/cancel/", booking_views.cancel_booking_html, name="booking_cancel_html"),
#
#     path("account/", account_views.account_dashboard, name="account_dashboard"),
#     path("account/delete/", account_views.delete_account, name="account_delete"),
#
#     prefix_default_language=False,
# )
#
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
