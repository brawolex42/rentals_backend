from django.core.management.base import BaseCommand
from pathlib import Path
import hashlib, time, random, re

try:
    import requests
except Exception:
    requests = None

CATS = ["exterior", "living", "bedroom", "kitchen", "bathroom"]

UNSPLASH_QUERIES = {
    "exterior":  ["house exterior", "modern house exterior", "german house exterior", "home facade"],
    "living":    ["living room interior", "modern living room", "cozy living room"],
    "bedroom":   ["bedroom interior", "modern bedroom", "cozy bedroom"],
    "kitchen":   ["kitchen interior", "modern kitchen", "white kitchen"],
    "bathroom":  ["bathroom interior", "modern bathroom", "shower bathroom"],
}

def _san(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)

def _unsplash_source_url(query: str, w=1600, h=1067):
    # без API-ключа, рандом по ключевому слову
    q = _san(query)
    return f"https://source.unsplash.com/{w}x{h}/?{q}"

def _pexels_search(q: str, per_page: int, page: int, api_key: str):
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": q, "per_page": per_page, "page": page, "orientation": "landscape"}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("photos", [])

class Command(BaseCommand):
    help = "Скачивает реальные фото домов/комнат по категориям в папку (static/real_images/<cat>). Источник: Unsplash Source (без ключа) или Pexels (нужен ключ)."

    def add_arguments(self, parser):
        parser.add_argument("--out-dir", type=str, default="static/real_images")
        parser.add_argument("--per-category", type=int, default=80, help="Сколько фото скачать на категорию.")
        parser.add_argument("--provider", choices=["unsplash", "pexels"], default="unsplash")
        parser.add_argument("--pexels-key", type=str, default=None, help="API ключ Pexels (если provider=pexels).")
        parser.add_argument("--sleep", type=float, default=0.1, help="Пауза между запросами.")
        parser.add_argument("--timeout", type=float, default=12.0, help="Таймаут запроса.")
        parser.add_argument("--cats", type=str, default=",".join(CATS), help="Список категорий через запятую.")

    def handle(self, *args, **opts):
        if requests is None:
            self.stderr.write(self.style.ERROR("Нужен requests: pip install requests"))
            return

        out_dir = Path(opts["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        cats = [c.strip() for c in opts["cats"].split(",") if c.strip()]
        per_cat = max(1, int(opts["per_category"]))
        provider = opts["provider"]
        pexels_key = opts.get("pexels_key")
        sleep_s = float(opts["sleep"])
        timeout = float(opts["timeout"])

        saved_total = 0

        for cat in cats:
            cat_dir = out_dir / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
            self.stdout.write(self.style.HTTP_INFO(f"Категория: {cat} → {cat_dir}"))

            if provider == "pexels":
                if not pexels_key:
                    self.stderr.write(self.style.ERROR("Нужен --pexels-key для provider=pexels"))
                    return
                # наберём фото из нескольких запросов
                need = per_cat
                page = 1
                while need > 0:
                    batch = _pexels_search(random.choice(UNSPLASH_QUERIES[cat]), per_page=min(80, need), page=page, api_key=pexels_key)
                    if not batch:
                        break
                    for ph in batch:
                        src = ph.get("src", {}).get("large")
                        if not src: continue
                        try:
                            r = requests.get(src, timeout=timeout, stream=True)
                            if r.status_code != 200: continue
                            h = hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]
                            ext = ".jpg"
                            fout = cat_dir / f"{cat}_{h}{ext}"
                            if fout.exists(): continue
                            with open(fout, "wb") as f:
                                for chunk in r.iter_content(65536):
                                    if chunk: f.write(chunk)
                            saved_total += 1
                            need -= 1
                        except Exception:
                            pass
                        time.sleep(sleep_s)
                    page += 1
            else:
                # unsplash source (random на каждый запрос)
                queries = UNSPLASH_QUERIES[cat]
                for i in range(per_cat):
                    q = random.choice(queries)
                    url = _unsplash_source_url(q)
                    try:
                        r = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
                        if r.status_code != 200:
                            time.sleep(sleep_s);
                            continue
                        src_url = r.url  # после редиректа
                        h = hashlib.sha1(src_url.encode("utf-8")).hexdigest()[:16]
                        fout = cat_dir / f"{cat}_{h}.jpg"
                        if fout.exists():
                            continue
                        with open(fout, "wb") as f:
                            for chunk in r.iter_content(65536):
                                if chunk: f.write(chunk)
                        saved_total += 1
                    except Exception:
                        pass
                    time.sleep(sleep_s)

        self.stdout.write(self.style.SUCCESS(f"Скачано файлов: {saved_total}. База: {out_dir.resolve()}"))
