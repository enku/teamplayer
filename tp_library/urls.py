from django.conf.urls import url

from teamplayer.library import views

urlpatterns = [
    url(r'^search/', views.song_search, name='library_search'),
    url(r'^add_to_queue', views.add_to_queue, name='library_add_to_queue'),
]
