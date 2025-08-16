from pathlib import Path
from io import BytesIO
import csv, requests, random
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction

User = get_user_model()

class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("--file", required=True)
        p.add_argument("--default-password", default="Passw0rd!")
        p.add_argument("--delimiter", default=",")
        p.add_argument("--encoding", default="utf-8")

    @transaction.atomic
    def handle(self, *a, **o):
        fp = Path(o["file"]).resolve()
        if not fp.exists():
            raise CommandError(f"Not found: {fp}")

        Property = apps.get_model("properties", "Property")
        PhotoModel = None
        for name in ("PropertyImage","PropertyPhoto","Photo","Image"):
            try:
                PhotoModel = apps.get_model("properties", name); break
            except LookupError:
                pass
        fields = {f.name for f in Property._meta.fields}

        with fp.open("r", encoding=o["encoding"], newline="") as f:
            reader = csv.DictReader(f, delimiter=o["delimiter"])
            created = 0
            for row in reader:
                owner = None
                uname = (row.get("owner_username") or "").strip()
                if "owner" in fields:
                    if uname:
                        owner, _ = User.objects.get_or_create(username=uname, defaults={"email": f"{uname}@example.com"})
                    else:
                        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
                        if owner is None:
                            owner = User.objects.create_user("demo_owner", "demo@example.com", o["default_password"])

                data = {}
                for k in ("title","name","description","city","district","address","postal_code","home_type"):
                    if k in fields and row.get(k): data[k] = row[k]
                for k in ("price","rooms","area"):
                    if k in fields and row.get(k): data[k] = type(getattr(Property, k).field.python_type())(row[k])
                if "is_active" in fields:
                    v = (row.get("is_active") or "true").strip().lower() in ("1","true","yes","y")
                    data["is_active"] = v
                if "owner" in fields and owner: data["owner"] = owner

                obj = Property.objects.create(**data)

                img_url = (row.get("image_url") or "").strip()
                if img_url:
                    try:
                        r = requests.get(img_url, timeout=15)
                        r.raise_for_status()
                        content = ContentFile(r.content, name=Path(img_url).name or f"img_{random.randint(1000,9999)}.jpg")
                        if "cover_image" in fields:
                            obj.cover_image.save(content.name, content, save=True)
                        elif "image" in fields:
                            obj.image.save(content.name, content, save=True)
                        elif PhotoModel:
                            pmf = {f.name for f in PhotoModel._meta.fields}
                            if "property" in pmf:
                                PhotoModel.objects.create(property=obj, image=content)
                            elif "listing" in pmf:
                                PhotoModel.objects.create(listing=obj, image=content)
                    except Exception:
                        pass
                created += 1

        self.stdout.write(str(created))
