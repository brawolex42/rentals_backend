import re
from django import template

register = template.Library()

_lat_re = re.compile(r"[A-Za-zÄÖÜäöüẞß\-'\s]+")

@register.filter
def clean_district(value):
    if not value:
        return ""
    m = _lat_re.findall(str(value))
    s = "".join(m).strip()
    return s
