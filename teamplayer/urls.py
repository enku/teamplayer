"""TeamPlayer URL dispatcher"""

from django.urls import include, re_path

from . import views

urlpatterns = [
    re_path(r"^about", views.about, name="about"),
    re_path(r"^teamplayer\.js$", views.js_object, name="js_object"),
    re_path(r"^crash/$", views.crash, name="crash"),
    re_path(r"^artist/(?P<artist>.*)/image$", views.artist_image, name="artist_image"),
    re_path(r"^artist/(?P<artist>.*)$", views.artist_page, name="artist_page"),
    re_path(r"^queue/$", views.show_queue, name="show_queue"),
    re_path(r"^queue/add$", views.add_to_queue, name="add_to_queue"),
    re_path(r"^queue/shuffle$", views.randomize_queue, name="randomize_queue"),
    re_path(r"^queue/clear", views.clear_queue, name="clear_queue"),
    re_path(r"^queue/order_by_rank$", views.order_by_rank, name="order_by_rank"),
    re_path(r"^queue/toggle$", views.toggle_queue_status, name="toggle_queue_status"),
    re_path(r"^auto/toggle$", views.toggle_auto_mode, name="toggle_auto_mode"),
    re_path("^reorder_queue$", views.reorder_queue, name="reorder_queue"),
    re_path(r"^queue/(\d+)$", views.show_entry, name="show_entry"),
    re_path(r"^player.html$", views.player, name="player"),
    re_path(r"^players/$", views.show_players, name="show_players"),
    re_path(r"^registration/$", views.registration, name="registration"),
    re_path(r"^register/$", views.register, name="register"),
    re_path(r"^logout$", views.logout, name="logout"),
    re_path(r"^currently_playing$", views.currently_playing, name="currently_playing"),
    re_path(r"^change_dj_name$", views.change_dj_name, name="change_dj_name"),
    re_path(r"^stations/$", views.show_stations, name="show_stations"),
    re_path(r"^stations/(\d+|mine)$", views.station_detail, name="station_detail"),
    re_path(r"^$", views.home, name="home"),
    re_path(r"^station/(\d+)/", views.home, name="station"),
    re_path(r"^station/prev", views.previous_station, name="previous_station"),
    re_path(r"^station/next", views.next_station, name="next_station"),
    re_path(r"^station/edit", views.edit_station, name="edit_station"),
    re_path(r"^station/create", views.create_station, name="create_station"),
    re_path(r"^library/", include("teamplayer.library.urls")),
]
