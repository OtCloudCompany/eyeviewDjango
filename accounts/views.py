from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import CustomUser
from .serializers import ChangePasswordSerializer, RegisterSerializer, LoginSerializer, UserSerializer
from django.contrib.auth import login
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import EmailTokenObtainPairSerializer
from rest_framework.pagination import PageNumberPagination

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer

class UsersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = CustomUser.objects.all().order_by('-id')
    serializer_class = UserSerializer

class ProfileDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    lookup_field = 'public_id'
    queryset = CustomUser.objects.all()


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, public_id): # <--- Accepts the UUID here 
        user_instance = get_object_or_404(CustomUser, public_id=public_id)
        # if request.user.public_id != public_id:
        #      return Response(
        #          {"detail": "Permission denied. Cannot update another user's profile."},
        #          status=status.HTTP_403_FORBIDDEN
        #      )
        serializer = UserSerializer(instance=user_instance, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response(UserSerializer(updated_user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateProfileView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RegisterSerializer


class ProfileDeleteView(generics.DestroyAPIView):
    """
    Handles the deletion of a user profile.
    Requires authentication. 
    """
    permission_classes = [IsAuthenticated]
    queryset = CustomUser.objects.all()
    lookup_field = 'public_id'

    def get_object(self):
        """
        Retrieves the profile and enforces that it belongs to the logged-in user.
        """
        try:
            obj = super().get_object()
        except CustomUser.DoesNotExist:
            raise
        return obj

class ChangePasswordView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):

        if request.user.public_id != public_id:
             return Response(
                 {"detail": "Action denied. Cannot change another user's password."},
                 status=status.HTTP_403_FORBIDDEN
             )
        try:
            user = CustomUser.objects.get(public_id=public_id)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_password = request.data.get('old_password')
        new_password = request.data.get('password')
        new_password2 = request.data.get('password2')

        # ✅ Validation
        if not all([old_password, new_password, new_password2]):
            return Response({'detail': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != new_password2:
            return Response({'detail': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        if not check_password(old_password, user.password):
            return Response({'detail': 'Old password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Update password
        user.set_password(new_password)
        user.save()

        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)

