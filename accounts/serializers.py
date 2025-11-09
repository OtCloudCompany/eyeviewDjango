from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


def get_public_id_for_user(user):
    """
    Retrieves the public_id for a user, handling potential errors.
    Assumes 'public_id' is the name of your UUID field on CustomUser.
    """
    # FIX: Ensure the attribute name is correct based on your model
    if hasattr(user, 'public_id'):
        return str(user.public_id)
    return None # Or raise an error if public_id is mandatory
    
    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT payload by adding the user's public_id.
    """
    @classmethod
    def get_token(cls, user):
        # Call the default token generation method
        token = super().get_token(user)

        # Add your custom claims to the token payload
        token['public_id'] = get_public_id_for_user(user) 
        
        # Optional: Add other data like first_name
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        token['email'] = user.email

        return token

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['public_id', 'email', 'first_name', 'last_name']


class RegisterSerializer(serializers.ModelSerializer):
    # password = serializers.CharField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = CustomUser
        # fields = ['first_name', 'last_name', 'email', 'password', ]
        fields = [
            'public_id', 'email', 'first_name', 'last_name', 'password'
        ]
        read_only_fields = ['public_id']

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    public_id = serializers.CharField()

    def validate(self, data):
        user = authenticate(email=data.get('email'), password=data.get('password'))
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        data['user'] = user
        return data

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims (optional)
        token['email'] = user.email
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        return token

    def validate(self, attrs):
        # Override to use email instead of username
        credentials = {
            'email': attrs.get('email'),
            'password': attrs.get('password'),
        }
        user = CustomUser.objects.filter(email=credentials['email']).first()
        if user and user.check_password(credentials['password']):
            refresh = self.get_token(user)
            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        raise serializers.ValidationError("Invalid credentials")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    password = serializers.CharField(required=True)
    password2 = serializers.CharField(required=True)

    def validate(self, data):
        # 1. Check if the new passwords match
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "New passwords must match."})
        return data