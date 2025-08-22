from django.core.management.base import BaseCommand
from django.db.models import Count
from src.properties.models import Property
import json

class Command(BaseCommand):
    help = "Show properties stats"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--city", type=str, default=None)
        parser.add_argument("--active", action="store_true")

    def handle(self, *args, **opts):
        qs = Property.objects.all()
        if opts.get("city"):
            qs = qs.filter(city__iexact=opts["city"])
        if opts.get("active"):
            qs = qs.filter(is_active=True)

        total = qs.count()
        active = qs.filter(is_active=True).count()
        with_photos = qs.filter(images__isnull=False).distinct().count()
        field_names = {f.name for f in Property._meta.get_fields()}
        with_address = qs.exclude(address_line="").count() if "address_line" in field_names else None
        by_city_rows = qs.values("city").annotate(c=Count("id")).order_by("city")
        by_city = { (r["city"] or "—"): r["c"] for r in by_city_rows }

        data = {
            "total": total,
            "active": active,
            "with_photos": with_photos,
            "with_address": with_address,
            "by_city": by_city,
        }

        if opts.get("json"):
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(f"Total: {data['total']}")
            self.stdout.write(f"Active: {data['active']}")
            self.stdout.write(f"With photos: {data['with_photos']}")
            if with_address is not None:
                self.stdout.write(f"With address: {data['with_address']}")
            self.stdout.write("By city:")
            for k, v in data["by_city"].items():
                self.stdout.write(f"  {k}: {v}")
