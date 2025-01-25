from django.contrib.auth.views import LoginView
from django.urls import include, path

urlpatterns = [
    path("accounts/login/", LoginView.as_view()),
    path("", include("teamplayer.urls")),
]
