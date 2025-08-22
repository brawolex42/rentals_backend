from django.core.management.base import BaseCommand
from django.db.models import Count
from src.properties.models import Property
from src.reviews.models import Review

class Command(BaseCommand):
    help = "Recount reviews_count on properties from actual reviews"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        batch_size = opts["batch"]

        cnts = dict(
            Review.objects.values("property_id")
            .annotate(c=Count("id"))
            .values_list("property_id", "c")
        )

        to_update = []
        updated = 0

        qs = Property.objects.all().only("id", "reviews_count")
        for p in qs.iterator():
            new_val = cnts.get(p.id, 0)
            if p.reviews_count != new_val:
                p.reviews_count = new_val
                to_update.append(p)
                if not dry and len(to_update) >= batch_size:
                    Property.objects.bulk_update(to_update, ["reviews_count"], batch_size=batch_size)
                    updated += len(to_update)
                    to_update.clear()

        if not dry and to_update:
            Property.objects.bulk_update(to_update, ["reviews_count"], batch_size=batch_size)
            updated += len(to_update)

        total_props = Property.objects.count()
        total_reviews = Review.objects.count()
        if dry:
            self.stdout.write(f"[DRY] Would update: {len([1 for p in qs if cnts.get(p.id,0)!=p.reviews_count])}")
        self.stdout.write(f"Updated properties: {updated}")
        self.stdout.write(f"Totals — properties: {total_props}, reviews: {total_reviews}")
