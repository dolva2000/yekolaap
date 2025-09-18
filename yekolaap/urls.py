from django.urls import path, include
from rest_framework.routers import DefaultRouter
from posts.views import PostViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.views.generic.base import RedirectView

router = DefaultRouter()
router.register(r"posts", PostViewSet, basename="post")

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/auth/", include("accounts.urls")),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Convenience redirect: /auth/ -> /api/auth/
    path("auth/", RedirectView.as_view(url="/api/auth/", permanent=False)),
]
