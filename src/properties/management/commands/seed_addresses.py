from django.core.management.base import BaseCommand
from src.properties.models import Property

# Словарь "Город → список адресов"
ADDRESSES = {
    "München": [
        "Leopoldstraße 45, 80802 München",
        "Sendlinger Straße 12, 80331 München",
        "Maximilianstraße 90, 80539 München"
    ],
    "Berlin": [
        "Alexanderplatz 1, 10178 Berlin",
        "Unter den Linden 55, 10117 Berlin",
        "Kurfürstendamm 100, 10709 Berlin"
    ],
    "Hamburg": [
        "Reeperbahn 5, 20359 Hamburg",
        "Speicherstadt 12, 20457 Hamburg",
        "Alsterufer 23, 20148 Hamburg"
    ],
    "Köln": [
        "Domstraße 4, 50667 Köln",
        "Hohenzollernring 72, 50672 Köln",
        "Severinstraße 199, 50676 Köln"
    ],
    "Frankfurt am Main": [
        "Zeil 10, 60313 Frankfurt am Main",
        "Westendstraße 1, 60325 Frankfurt am Main",
        "Bockenheimer Landstraße 24, 60323 Frankfurt am Main"
    ],
    "Dresden": [
        "Altmarkt 17, 01067 Dresden",
        "Prager Straße 5, 01069 Dresden",
        "Königsbrücker Straße 55, 01099 Dresden"
    ],
    "Stuttgart": [
        "Königstraße 20, 70173 Stuttgart",
        "Schlossplatz 1, 70173 Stuttgart",
        "Rotebühlstraße 121, 70178 Stuttgart"
    ]
}


class Command(BaseCommand):
    help = "Добавляет адреса объектам недвижимости"

    def handle(self, *args, **options):
        updated = 0

        for city, addresses in ADDRESSES.items():
            props = Property.objects.filter(city=city, address__isnull=True) | Property.objects.filter(city=city, address="")
            for i, prop in enumerate(props):
                prop.address = addresses[i % len(addresses)]
                prop.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Обновлено {updated} объектов с адресами"))
