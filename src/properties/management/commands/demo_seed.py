from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        Property = apps.get_model("properties", "Property")
        owner = User.objects.filter(is_superuser=True).first() or User.objects.create_superuser(
            "admin", "admin@example.com", "admin12345"
        )
        cities = ["Berlin","Muenchen","Hamburg","Koeln","Frankfurt","Stuttgart","Duesseldorf","Dortmund","Essen","Leipzig","Bremen","Dresden","Hannover","Nuernberg","Duisburg","Bochum","Wuppertal","Bielefeld","Bonn","Muenster"]
        areas = [28,35,45,55,65,75,85,95,110,125]
        prices = [550,650,780,920,1050,1200,1350,1500,1750,2000]
        rooms = [1,2,3,4,5]
        types = ["apartment","house","studio","room"]
        batch = []
        n = int(opts["count"])
        for i in range(n):
            c = cities[i % len(cities)]
            r = rooms[i % len(rooms)]
            a = areas[i % len(areas)]
            p = prices[i % len(prices)]
            t = types[i % len(types)]
            batch.append(Property(
                owner=owner,
                title=f"{c}: {r}-room, {a} sqm",
                description=f"{c}: central, bright",
                city=c,
                district="Mitte",
                price=p,
                rooms=r,
                property_type=t,
                is_active=True,
            ))
        Property.objects.bulk_create(batch)
        self.stdout.write(f"created: {len(batch)}")
