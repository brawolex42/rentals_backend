from django.core.management.base import BaseCommand
from src.properties.models import Property

ADDRESSES = {
    "Berlin": [("Alexanderplatz 1", "10178"), ("Unter den Linden 77", "10117"), ("Kurfürstendamm 226", "10719")],
    "München": [("Leopoldstraße 45", "80802"), ("Sendlinger Straße 12", "80331"), ("Maximilianstraße 34", "80539")],
    "Hamburg": [("Reeperbahn 5", "20359"), ("Jungfernstieg 16", "20354"), ("Mönckebergstraße 7", "20095")],
    "Köln": [("Domkloster 4", "50667"), ("Breite Straße 80", "50667"), ("Aachener Straße 1253", "50858")],
    "Frankfurt am Main": [("Zeil 10", "60313"), ("Bockenheimer Landstraße 24", "60323"), ("Westendstraße 1", "60325")],
    "Düsseldorf": [("Königsallee 60", "40212"), ("Schadowstraße 17", "40212"), ("Berliner Allee 45", "40212")],
    "Stuttgart": [("Königstraße 20", "70173"), ("Schlossplatz 1", "70173"), ("Rotebühlstraße 121", "70178")],
    "Dresden": [("Altmarkt 17", "01067"), ("Prager Straße 5", "01069"), ("Neumarkt 2", "01067")],
    "Leipzig": [("Grimmaische Straße 12", "04109"), ("Petersstraße 36", "04109"), ("Augustusplatz 8", "04109")],
    "Nürnberg": [("Königstraße 28", "90402"), ("Karolinenstraße 45", "90402"), ("Färberstraße 1", "90402")],
    "Bremen": [("Sögestraße 44", "28195"), ("Obernstraße 50", "28195"), ("Am Markt 1", "28195")],
    "Hannover": [("Bahnhofstraße 3", "30159"), ("Georgstraße 20", "30159"), ("Lister Meile 45", "30161")],
    "Dortmund": [("Westenhellweg 60", "44137"), ("Kleppingstraße 4", "44135"), ("Kampstraße 1", "44137")],
    "Essen": [("Kettwiger Straße 31", "45127"), ("Limbecker Platz 1a", "45127"), ("Rottstraße 5", "45127")],
    "Augsburg": [("Maximilianstraße 40", "86150"), ("Annastraße 22", "86150"), ("Hermannstraße 7", "86150")],
    "Bonn": [("Sternstraße 58", "53111"), ("Markt 10", "53111"), ("Oxfordstraße 12", "53111")],
    "Karlsruhe": [("Kaiserstraße 150", "76133"), ("Marktplatz 1", "76133"), ("Waldstraße 20", "76133")],
    "Wiesbaden": [("Kirchgasse 6", "65183"), ("Langgasse 20", "65183"), ("Wilhelmstraße 34", "65183")],
    "Bochum": [("Kortumstraße 5", "44787"), ("Huestraße 30", "44787"), ("Dr.-Ruer-Platz 2", "44787")],
    "Bielefeld": [("Bahnhofstraße 28", "33602"), ("Niedernstraße 5", "33602"), ("Obernstraße 46", "33602")],
    "Gelsenkirchen": [("Bahnhofstraße 56", "45879"), ("Neumarkt 1", "45879"), ("Ahstraße 12", "45879")],
    "Mannheim": [("Planken O5 7", "68161"), ("Paradeplatz 1", "68161"), ("Kurpfalzstraße 10", "68161")],
    "Münster": [("Prinzipalmarkt 25", "48143"), ("Salzstraße 36", "48143"), ("Windthorststraße 7", "48143")],
    "Wuppertal": [("Alte Freiheit 20", "42103"), ("Neumarkt 10", "42103"), ("Poststraße 5", "42103")],
    "Duisburg": [("Königstraße 48", "47051"), ("Friedrich-Wilhelm-Straße 82", "47051"), ("Kuhtor 1", "47051")],
}

def is_blank(v):
    return v is None or str(v).strip() == ""

def gen_fallback_address(prop, i):
    streets = ["Musterstraße", "Hauptstraße", "Bahnhofstraße", "Gartenweg", "Schillerstraße", "Goethestraße", "Parkallee", "Lindenweg"]
    street = streets[i % len(streets)]
    house = (i % 120) + 1
    plz = str(10000 + (prop.id % 90000)).zfill(5)
    return f"{street} {house}", plz

class Command(BaseCommand):
    help = "Fill address_line and postal_code for properties"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--cities", type=str, default="")

    def handle(self, *args, **opts):
        overwrite = opts.get("overwrite", False)
        limit = int(opts.get("limit") or 0)
        cities_opt = opts.get("cities", "").strip()
        qs = Property.objects.all()
        if cities_opt:
            wanted = [c.strip() for c in cities_opt.split(",") if c.strip()]
            qs = qs.filter(city__in=wanted)
        if not overwrite:
            qs = qs.filter(address_line__in=["", None]) | Property.objects.filter(postal_code__in=["", None])
        qs = qs.order_by("id")
        if limit > 0:
            qs = qs[:limit]
        updated = 0
        for prop in qs:
            city_list = ADDRESSES.get(prop.city)
            if city_list:
                idx = updated % len(city_list)
                street, plz = city_list[idx]
            else:
                street, plz = gen_fallback_address(prop, updated)
            if overwrite or is_blank(prop.address_line):
                prop.address_line = street
            if overwrite or is_blank(prop.postal_code):
                prop.postal_code = plz
            prop.save(update_fields=["address_line", "postal_code", "updated_at"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} properties"))
