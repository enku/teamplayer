from django.conf.urls import include, url

from django.contrib.auth.views import LoginView

urlpatterns = [
    url(r'^accounts/login/$', LoginView.as_view()),
    url(r'', include('teamplayer.urls')),
]
