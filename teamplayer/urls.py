"""TeamPlayer URL dispatcher"""
from django.conf.urls import include, url

from . import views

urlpatterns = [
    url(r"^about", views.about, name="about"),
    url(r"^teamplayer\.js$", views.js_object, name="js_object"),
    url(r"^crash/$", views.crash, name="crash"),
    url(r"^artist/(?P<artist>.*)/image$", views.artist_image, name="artist_image"),
    url(r"^artist/(?P<artist>.*)$", views.artist_page, name="artist_page"),
    url(r"^queue/$", views.show_queue, name="show_queue"),
    url(r"^queue/add$", views.add_to_queue, name="add_to_queue"),
    url(r"^queue/shuffle$", views.randomize_queue, name="randomize_queue"),
    url(r"^queue/clear", views.clear_queue, name="clear_queue"),
    url(r"^queue/order_by_rank$", views.order_by_rank, name="order_by_rank"),
    url(r"^queue/toggle$", views.toggle_queue_status, name="toggle_queue_status"),
    url(r"^auto/toggle$", views.toggle_auto_mode, name="toggle_auto_mode"),
    url("^reorder_queue$", views.reorder_queue, name="reorder_queue"),
    url(r"^queue/(\d+)$", views.show_entry, name="show_entry"),
    url(r"^player.html$", views.player, name="player"),
    url(r"^players/$", views.show_players, name="show_players"),
    url(r"^registration/$", views.registration, name="registration"),
    url(r"^register/$", views.register, name="register"),
    url(r"^logout$", views.logout, name="logout"),
    url(r"^currently_playing$", views.currently_playing, name="currently_playing"),
    url(r"^change_dj_name$", views.change_dj_name, name="change_dj_name"),
    url(r"^stations/$", views.show_stations, name="show_stations"),
    url(r"^stations/(\d+|mine)$", views.station_detail, name="station_detail"),
    url(r"^$", views.home, name="home"),
    url(r"^station/(\d+)/", views.home, name="station"),
    url(r"^station/prev", views.previous_station, name="previous_station"),
    url(r"^station/next", views.next_station, name="next_station"),
    url(r"^station/edit", views.edit_station, name="edit_station"),
    url(r"^station/create", views.create_station, name="create_station"),
    url(r"^library/", include("teamplayer.library.urls")),
]
