from django.conf.urls import patterns, url

urlpatterns = patterns(
    '',
    url(r'^search/', 'tp_library.views.song_search', name='tp_library_search'),
    url(r'^add_to_queue', 'tp_library.views.add_to_queue'),
    url(r'^song/(\d+)$', 'tp_library.views.get_song'),
    url(r'^feeds/(\d+)/rss$', 'tp_library.views.feed'),
)
