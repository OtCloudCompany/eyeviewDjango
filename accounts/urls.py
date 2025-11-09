from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import ChangePasswordView, CreateProfileView, ProfileDeleteView, ProfileDetailView, RegisterView, UpdateProfileView, UsersView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('user-profiles/', UsersView.as_view(), name='user_profiles'),
    path('create-profile/', CreateProfileView.as_view(), name='create_profile'),
    path('<uuid:public_id>/', ProfileDetailView.as_view(), name='profile_detail'),
    path('<uuid:public_id>/update-profile/', UpdateProfileView.as_view(), name='update_profile'),
    path('<uuid:public_id>/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('<uuid:public_id>/delete/', ProfileDeleteView.as_view(), name='delete_profile'),
    
]
