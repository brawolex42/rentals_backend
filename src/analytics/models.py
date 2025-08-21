from django.db import models
from django.conf import settings


class SearchQuery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_search_queries",
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    query = models.CharField(max_length=255)
    path = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["ip"]),
            models.Index(fields=["query"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.query


class ViewEvent(models.Model):
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="view_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_view_events",
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True, default="")
    url = models.URLField(blank=True, default="")
    user_agent = models.CharField(max_length=500, blank=True, default="")
    referer = models.CharField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["ip"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"View #{self.pk} of {self.property_id}"


class InterestEvent(models.Model):
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="interest_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_interest_events",
    )
    kind = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["kind"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Interest #{self.pk} {self.kind}"
