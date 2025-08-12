from django.db import models

class UserRole(models.TextChoices):
    TENANT = 'tenant', 'Арендатор'
    LANDLORD = 'landlord', 'Арендодатель'

class PropertyType(models.TextChoices):
    APARTMENT = 'apartment', 'Квартира'
    HOUSE = 'house', 'Дом'
    STUDIO = 'studio', 'Студия'
    OTHER = 'other', 'Другое'

class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'В ожидании'
    CONFIRMED = 'confirmed', 'Подтверждено'
    DECLINED = 'declined', 'Отклонено'
    CANCELED = 'canceled', 'Отменено'
