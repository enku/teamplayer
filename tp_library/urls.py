from django.conf.urls import url

from tp_library import views

urlpatterns = [
    url(r'^search/', views.song_search, name='library_search'),
    url(r'^add_to_queue', views.add_to_queue, name='library_add_to_queue'),
    url(r'^song/(\d+)$', views.get_song, name='library_get_song'),
    url(r'^feeds/(\d+)/rss$', views.feed, name='library_feed'),
]
