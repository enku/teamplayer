from django.contrib.auth.views import LoginView
from django.urls import include, re_path

urlpatterns = [
    re_path(r"^accounts/login/$", LoginView.as_view()),
    re_path(r"", include("teamplayer.urls")),
]
