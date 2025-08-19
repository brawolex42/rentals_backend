from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import IntegrityError

User = get_user_model()

def _generate_unique_username(base: str) -> str:
    base = (base or "").strip()
    if not base:
        base = "user"
    base = base.replace(" ", "_")
    if len(base) > 30:
        base = base[:30]
    candidate = base
    idx = 0
    while User.objects.filter(username=candidate).exists():
        idx += 1
        suffix = str(idx)
        trim = 30 - len(suffix) - 1
        if trim < 1:
            trim = 1
        candidate = f"{base[:trim]}-{suffix}"
    return candidate

def register_html(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        username = (request.POST.get("username") or "").strip()
        password1 = request.POST.get("password1") or request.POST.get("password") or ""
        password2 = request.POST.get("password2") or request.POST.get("password") or ""
        next_url = request.GET.get("next") or request.POST.get("next") or settings.LOGIN_REDIRECT_URL or "/"
        if not email or not password1 or not password2:
            messages.error(request, "Please fill in all required fields.")
            return render(request, "users/register.html", {"email": email, "username": username, "next": next_url})
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "users/register.html", {"email": email, "username": username, "next": next_url})
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, "users/register.html", {"email": email, "username": username, "next": next_url})
        if not username:
            username = email.split("@")[0]
        username = _generate_unique_username(username)
        try:
            user = User.objects.create_user(email=email, username=username, password=password1)
        except IntegrityError:
            username = _generate_unique_username(username)
            user = User.objects.create_user(email=email, username=username, password=password1)
        user = authenticate(request, username=email, password=password1)
        if user is not None:
            login(request, user)
            return redirect(next_url)
        messages.success(request, "Registration completed. Please sign in.")
        return redirect(settings.LOGIN_URL)
    next_url = request.GET.get("next") or ""
    return render(request, "users/register.html", {"next": next_url})

def login_html(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        next_url = request.GET.get("next") or request.POST.get("next") or settings.LOGIN_REDIRECT_URL or "/"
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url)
        messages.error(request, "Invalid email or password.")
        return render(request, "users/login.html", {"email": email, "next": next_url})
    next_url = request.GET.get("next") or ""
    return render(request, "users/login.html", {"next": next_url})

def logout(request):
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL or "/")

@login_required
def account_dashboard(request):
    return render(request, "users/account.html")

@login_required
def delete_account(request):
    if request.method == "POST":
        u = request.user
        auth_logout(request)
        u.delete()
        messages.success(request, "Account deleted.")
        return redirect("/")
    return render(request, "users/account.html", {"confirm_delete": True})
