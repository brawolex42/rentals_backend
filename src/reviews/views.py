from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils.translation import gettext as _
from rest_framework import viewsets, permissions
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer


@login_required
@require_POST
def submit_review(request, pk: int):
    prop_id = pk
    rating = request.POST.get("rating")
    text = request.POST.get("text", "")
    back_url = f"{reverse('property_detail', args=[prop_id])}#reviews"
    serializer = ReviewCreateSerializer(
        data={"property": prop_id, "rating": rating, "text": text},
        context={"request": request},
    )
    if serializer.is_valid():
        review = serializer.save()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "id": review.id, "rating": review.rating, "text": review.text}, status=201)
        messages.success(request, _("Thank you! Your review has been saved."))
        return redirect(back_url)
    errors = serializer.errors
    msg = next(iter(errors.values()))[0] if errors else _("Could not save the review.")
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "errors": errors}, status=400)
    messages.error(request, msg)
    return redirect(back_url)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("author", "property").all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == "create":
            return ReviewCreateSerializer
        return ReviewSerializer
