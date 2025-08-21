from django import template

register = template.Library()

@register.simple_tag
def card_cover(prop):
    try:
        imgs = list(prop.images.all())
    except Exception:
        imgs = []
    if not imgs:
        return None

    def is_pexels(im):
        name = ""
        try:
            name = (im.image.name or "")
        except Exception:
            try:
                name = (im.image.url or "")
            except Exception:
                name = ""
        return "pexels_" in name.lower()

    pool = [im for im in imgs if is_pexels(im)] or imgs
    idx = (prop.pk or 0) % len(pool)
    return pool[idx]
