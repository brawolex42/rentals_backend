from django.contrib.auth.models import AbstractUser
from django.db import models
from src.shared.enums import UserRole

class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.TENANT)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username оставим техническим

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"
