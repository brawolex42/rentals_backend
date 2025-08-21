from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
import random
from pathlib import Path

from src.properties.models import Property, OwnerContact

try:
    from faker import Faker
except Exception:
    Faker = None


def fake_phone_de():
    head = random.choice(["+49151", "+49152", "+49157", "+49160", "+49162", "+49172", "+49173", "+49176", "+49177"])
    tail = "".join(random.choice("0123456789") for _ in range(7))
    return head + tail


def fake_telegram(username_base: str):
    base = username_base or "vermieter"
    return f"{base}_home"


class Command(BaseCommand):
    help = "Создаёт фейковые контакты OwnerContact для всех владельцев объектов в Германии"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--lang", type=str, default="de")

    @transaction.atomic
    def handle(self, *args, **opts):
        overwrite = opts["overwrite"]
        lang = opts["lang"]
        fake = Faker("de_DE") if Faker else None

        owner_ids = list(
            Property.objects.values_list("owner_id", flat=True).distinct()
        )
        User = get_user_model()
        users = User.objects.filter(id__in=owner_ids)

        created, updated = 0, 0
        for u in users:
            data = {
                "email_public": u.email or "",
                "phone": fake_phone_de(),
                "whatsapp": fake_phone_de(),
                "telegram": fake_telegram(getattr(u, "username", "vermieter")),
                "website": "",
                "available_hours": "09:00–18:00 CET",
                "preferred_language": lang,
            }
            obj, exists = OwnerContact.objects.get_or_create(user=u, defaults=data)
            if exists:
                created += 1
            else:
                if overwrite:
                    for k, v in data.items():
                        setattr(obj, k, v)
                    obj.save(update_fields=list(data.keys()))
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Готово: создано {created}, обновлено {updated}"))
