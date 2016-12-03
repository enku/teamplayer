from django.conf.urls import include, url

from django.contrib.auth.views import login as django_login

urlpatterns = [
    url(r'^accounts/login/$', django_login),
    url(r'', include('teamplayer.urls')),
]
