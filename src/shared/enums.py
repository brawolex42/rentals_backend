from django.db.models import TextChoices


class UserRole(TextChoices):
    ADMIN = "ADMIN", "Admin"
    HOST = "HOST", "Host"
    TENANT = "TENANT", "Tenant"


class BookingStatus(TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    ACTIVE = "ACTIVE", "Active"
    APPROVED = "APPROVED", "Approved"
    BOOKED = "BOOKED", "Booked"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    OVERDUE = "OVERDUE", "Overdue"
    COMPLETED = "COMPLETED", "Completed"
    CANCELED = "CANCELED", "Canceled"

# для совместимости, если в коде встречается CANCELLED
BookingStatus.CANCELLED = BookingStatus.CANCELED


class PropertyType(TextChoices):
    APARTMENT = "APARTMENT", "Apartment"
    HOUSE = "HOUSE", "House"
    STUDIO = "STUDIO", "Studio"
    VILLA = "VILLA", "Villa"
    ROOM = "ROOM", "Room"
