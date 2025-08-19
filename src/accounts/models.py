from django.contrib.auth.models import AbstractUser
from django.db import models
from src.shared.enums import UserRole

class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.TENANT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def get_display_name(self):
        name = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        if name or last:
            candidate = (name + " " + last).strip()
        else:
            candidate = (self.username or "").strip() or "User"
        if "@" in candidate:
            local = candidate.split("@", 1)[0]
            if len(local) <= 2:
                return (local[:1] + "*" * max(len(local) - 1, 0)) or "User"
            return f"{local[0]}***{local[-1]}"
        return candidate

    def __str__(self):
        return f"{self.get_display_name()} ({self.role})"
