from django.conf.urls import url

from tp_library import views

urlpatterns = [
    url(r'^search/', views.song_search, name='tp_library_search'),
    url(r'^add_to_queue', views.add_to_queue),
    url(r'^song/(\d+)$', views.get_song),
    url(r'^feeds/(\d+)/rss$', views.feed),
]
