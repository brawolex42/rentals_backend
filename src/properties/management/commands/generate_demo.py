import random
from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.auth import get_user_model
from faker import Faker

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    def handle(self, *args, **options):
        Property = apps.get_model("properties", "Property")
        fields = {f.name for f in Property._meta.fields}
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not owner:
            owner = User.objects.create_superuser("admin","admin@example.com","admin12345")
        fake = Faker(["ru_RU","de_DE","en_US"])
        cities = [
            "Berlin","Hamburg","München","Köln","Frankfurt","Stuttgart","Düsseldorf","Dresden","Leipzig","Hannover",
            "Moscow","Saint Petersburg","Kazan","Sochi","Novosibirsk","Yekaterinburg","Krasnodar","Voronezh","Kaliningrad",
            "London","Manchester","Bristol","Leeds","Liverpool","Edinburgh","Birmingham","Glasgow","Oxford","Cambridge"
        ]
        types = ["apartment","house","studio","room"]
        created = 0
        for _ in range(options["count"]):
            city = random.choice(cities)
            district = fake.city_suffix()
            address = fake.street_address()
            rooms = random.choice([1,2,3,4,5])
            price = random.choice([650,790,920,1100,1350,1600,2000,2400,2850])
            property_type = random.choice(types)
            title = f"{city}: {rooms} комн."
            description = f"{address}, {city}. {rooms} комн., цена €{price}"
            data = {}
            if "title" in fields: data["title"] = title
            if "description" in fields: data["description"] = description
            if "city" in fields: data["city"] = city
            if "district" in fields: data["district"] = district
            if "price" in fields: data["price"] = price
            if "rooms" in fields: data["rooms"] = rooms
            if "property_type" in fields: data["property_type"] = property_type
            if "is_active" in fields: data["is_active"] = True
            if "owner" in fields: data["owner"] = owner
            try:
                Property.objects.create(**data)
                created += 1
            except Exception as e:
                self.stderr.write(f"skip: {e}")
        self.stdout.write(f"Создано {created} объектов")
