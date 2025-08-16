from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers

User = get_user_model()
token_generator = PasswordResetTokenGenerator()

def _uid_encode(pk: int) -> str:
    return urlsafe_base64_encode(force_bytes(pk))

def _uid_decode(uid: str) -> int:
    return int(urlsafe_base64_decode(uid).decode("utf-8"))

def _activation_link(user: User) -> str:
    uid = _uid_encode(user.pk)
    token = token_generator.make_token(user)
    return f"{settings.BACKEND_URL}/api/accounts/verify-email/?uid={uid}&token={token}"

def _password_reset_link(user: User) -> str:
    uid = _uid_encode(user.pk)
    token = token_generator.make_token(user)
    return f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

def _send_activation_email(user: User) -> None:
    link = _activation_link(user)
    subject = "Подтвердите e-mail"
    context = {"user": user, "activation_link": link}
    html = render_to_string("emails/activation.html", context)
    text = f"Для активации аккаунта перейдите по ссылке:\n{link}"
    email = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html, "text/html")
    email.send()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ("username", "email", "password")
    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_active=False,
        )

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

class ResendActivationSerializer(serializers.Serializer):
    email = serializers.EmailField()

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        _send_activation_email(user)
        return Response({"detail": "Пользователь создан. Проверьте почту для активации."}, status=status.HTTP_201_CREATED)

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        uid = request.query_params.get("uid")
        token = request.query_params.get("token")
        if not uid or not token:
            return Response({"detail": "Некорректная ссылка."}, status=400)
        try:
            user = User.objects.get(pk=_uid_decode(uid))
        except Exception:
            return Response({"detail": "Пользователь не найден."}, status=400)
        if token_generator.check_token(user, token):
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
            return Response({"detail": "Email подтверждён."})
        return Response({"detail": "Токен недействителен или истёк."}, status=400)

class ResendActivationView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        s = ResendActivationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Если email существует, письмо отправлено."})
        if user.is_active:
            return Response({"detail": "Email уже подтверждён."})
        _send_activation_email(user)
        return Response({"detail": "Письмо отправлено повторно."})

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Если email существует, письмо отправлено."})
        link = _password_reset_link(user)
        subject = "Сброс пароля"
        context = {"user": user, "reset_link": link}
        html = render_to_string("emails/reset.html", context)
        text = f"Для сброса пароля перейдите по ссылке:\n{link}"
        email_msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [email])
        email_msg.attach_alternative(html, "text/html")
        email_msg.send()
        return Response({"detail": "Если email существует, письмо отправлено."})

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        try:
            user = User.objects.get(pk=_uid_decode(uid))
        except Exception:
            return Response({"detail": "Некорректная ссылка."}, status=400)
        if token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save(update_fields=["password"])
            return Response({"detail": "Пароль обновлён."})
        return Response({"detail": "Токен недействителен или истёк."}, status=400)

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        u = request.user
        return Response({"id": u.id, "username": u.get_username(), "email": u.email, "is_active": u.is_active})
