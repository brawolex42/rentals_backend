def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def ensure_session(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key
