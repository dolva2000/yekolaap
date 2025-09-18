from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers
from accounts.models import Profile


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        full_name = validated_data.get("full_name")
        email = validated_data.get("email").lower()
        phone = validated_data.get("phone", "")
        password = validated_data.get("password")

        # Use email as username for simplicity
        user = User(username=email, email=email)
        # Try to split full name
        try:
            first_name, last_name = full_name.strip().split(" ", 1)
        except ValueError:
            first_name, last_name = full_name, ""
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(password)
        user.save()

        Profile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name, "phone": phone},
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email").lower()
        password = attrs.get("password")
        # Authenticate using username=email (as set at registration)
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    phone = serializers.CharField(source="profile.phone", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name", "phone"]
