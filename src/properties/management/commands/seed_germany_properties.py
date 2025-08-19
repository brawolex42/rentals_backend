from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal
import random

try:
    from faker import Faker
    FAKE = Faker("de_DE")
except Exception:
    FAKE = None

GERMAN_CITIES = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", "Stuttgart",
    "Düsseldorf", "Dortmund", "Essen", "Leipzig", "Bremen", "Dresden",
    "Hannover", "Nürnberg", "Duisburg", "Bochum", "Wuppertal", "Bielefeld",
    "Bonn", "Münster", "Karlsruhe", "Mannheim", "Augsburg", "Wiesbaden",
    "Gelsenkirchen", "Mönchengladbach", "Braunschweig", "Chemnitz",
]

HOUSE_TITLES = [
    "Gemütliches Einfamilienhaus", "Modernes Stadthaus", "Ruhiges Reihenhaus",
    "Helles Familienhaus", "Charmantes Haus mit Garten"
]
APARTMENT_TITLES = [
    "Moderne Stadtwohnung", "Helle 2-Zimmer-Wohnung", "Komfortables Apartment",
    "Loft im Zentrum", "Gemütliche Altbauwohnung"
]

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _set_if_exists(obj, **kwargs):
    for k, v in kwargs.items():
        if v is None:
            continue
        if _has_field(obj.__class__, k):
            setattr(obj, k, v)

def _pick_owner(explicit_username: str | None):
    User = get_user_model()
    if explicit_username:
        try:
            return User.objects.get(**{User.USERNAME_FIELD: explicit_username})
        except User.DoesNotExist:
            pass
    # 1) попробуем активного staff/superuser
    q = User.objects.filter(is_active=True).order_by("-is_staff", "-is_superuser", "id")
    owner = q.first()
    if owner:
        return owner
    # 2) если совсем пусто — создадим демо-пользователя
    username_field = User.USERNAME_FIELD
    demo_username = "demo_owner"
    defaults = {username_field: demo_username}
    owner = User.objects.create_user(**defaults, password="demo_owner123")
    return owner

class Command(BaseCommand):
    help = "Создаёт тестовые объекты недвижимости (дома и квартиры) только в Германии."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20, help="Сколько объектов создать (по умолчанию 20).")
        parser.add_argument("--images", action="store_true",
                            help="Создавать записи PropertyImage (если модель есть).")
        parser.add_argument("--min", dest="min_price", type=int, default=600,
                            help="Минимальная цена (€/мес). По умолчанию 600.")
        parser.add_argument("--max", dest="max_price", type=int, default=3200,
                            help="Максимальная цена (€/мес). По умолчанию 3200.")
        parser.add_argument("--owner", type=str, default=None,
                            help="username владельца для присвоения объектам (если не указан — берётся первый активный пользователь, иначе создаётся demo_owner).")

    def handle(self, *args, **opts):
        count = int(opts["count"])
        with_images = bool(opts["images"])
        min_price = int(opts["min_price"])
        max_price = int(opts["max_price"])
        owner = _pick_owner(opts.get("owner"))

        Property = apps.get_model("properties", "Property")
        PropertyImage = None
        try:
            PropertyImage = apps.get_model("properties", "PropertyImage")
        except Exception:
            pass

        created = 0
        for i in range(count):
            sid = transaction.savepoint()
            try:
                is_apartment = (i % 2 == 0)
                city = random.choice(GERMAN_CITIES)
                street = f"{random.randint(1, 28)}. {(FAKE.street_name() if FAKE else 'Musterstraße')}"
                zipcode = FAKE.postcode() if FAKE else "10115"

                title = random.choice(APARTMENT_TITLES if is_apartment else HOUSE_TITLES)
                prop_type = None
                if _has_field(Property, "property_type"):
                    prop_type = "apartment" if is_apartment else "house"

                price_month = Decimal(random.randrange(min_price, max_price + 1))
                rooms = random.randint(1, 5)

                prop = Property()
                # обязательные/частые поля
                _set_if_exists(
                    prop,
                    title=title,
                    description=(FAKE.paragraph(nb_sentences=3) if FAKE else "Schöne Immobilie in guter Lage."),
                    city=city,
                    address=f"{street}, {zipcode} {city}",
                    address_line=f"{street}, {zipcode} {city}",
                    country="Germany",
                    price=price_month,
                    price_per_month=price_month,
                    price_per_night=(price_month / 30),
                    rooms=rooms,
                    bedrooms=(rooms - 1) if rooms > 1 else None,
                    bathrooms=1,
                    property_type=prop_type,
                    is_active=True,
                    rating_avg=Decimal("0.0"),
                    reviews_total=0,
                    max_guests=min(rooms + 1, 6),
                    display_district=(FAKE.city_suffix() if FAKE else None),
                )

                # владельцы/создатели — ставим во все возможные поля
                _set_if_exists(prop, owner=owner, host=owner, created_by=owner, user=owner)

                prop.save()

                if with_images and PropertyImage and _has_field(PropertyImage, "property"):
                    try:
                        img = PropertyImage(property=prop)
                        _set_if_exists(img, caption="Außenansicht", address_line=getattr(prop, "address", None))
                        # image поле пропустим (если обязательное — БД сама скажет)
                        img.save()
                    except Exception as e:
                        self.stderr.write(self.style.WARNING(f"Картинка для объекта {prop.pk} пропущена: {e}"))

                transaction.savepoint_commit(sid)
                created += 1
            except Exception as e:
                transaction.savepoint_rollback(sid)
                self.stderr.write(self.style.ERROR(f"Не удалось сохранить объект #{i+1}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Создано объектов: {created} (только Германия)."))
