import os

def admin_contact(request):
    return {
        "admin_contact": {
            "email": os.getenv("ADMIN_EMAIL", "admin@rentals.com"),
            "phone": os.getenv("ADMIN_PHONE", "+49 160 1234567"),
            "hours": os.getenv("ADMIN_HOURS", "Mo–Fr 09:00–18:00"),
            "whatsapp": os.getenv("ADMIN_WHATSAPP", "491601234567"),
            "telegram": os.getenv("ADMIN_TELEGRAM", "rentals_support"),
        }
    }
