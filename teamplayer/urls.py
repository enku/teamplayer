"""TeamPlayer URL dispatcher"""

from django.urls import include, path

from . import views

urlpatterns = [
    path("about", views.about, name="about"),
    path("teamplayer.js", views.js_object, name="js_object"),
    path("crash/", views.crash, name="crash"),
    path("artist/<str:artist>/image", views.artist_image, name="artist_image"),
    path("artist/<str:artist>", views.artist_page, name="artist_page"),
    path("queue/", views.show_queue, name="show_queue"),
    path("queue/add", views.add_to_queue, name="add_to_queue"),
    path("queue/shuffle", views.randomize_queue, name="randomize_queue"),
    path("queue/clea", views.clear_queue, name="clear_queue"),
    path("queue/order_by_rank", views.order_by_rank, name="order_by_rank"),
    path("queue/toggle", views.toggle_queue_status, name="toggle_queue_status"),
    path("auto/toggle", views.toggle_auto_mode, name="toggle_auto_mode"),
    path("reorder_queue", views.reorder_queue, name="reorder_queue"),
    path("queue/<int:entry_id>", views.show_entry, name="show_entry"),
    path("player.html", views.player, name="player"),
    path("players/", views.show_players, name="show_players"),
    path("registration/", views.registration, name="registration"),
    path("register/", views.register, name="register"),
    path("logout", views.logout, name="logout"),
    path("currently_playing", views.currently_playing, name="currently_playing"),
    path("change_dj_name", views.change_dj_name, name="change_dj_name"),
    path("stations/", views.show_stations, name="show_stations"),
    path("stations/<int:station_id>", views.station_detail, name="station_detail"),
    path(
        "stations/mine", views.station_detail, {"station_id": "mine"}, name="my_station"
    ),
    path("", views.home, name="home"),
    path("station/<int:station_id>/", views.home, name="station"),
    path("station/prev", views.previous_station, name="previous_station"),
    path("station/next", views.next_station, name="next_station"),
    path("station/edit", views.edit_station, name="edit_station"),
    path("station/create", views.create_station, name="create_station"),
    path("library/", include("teamplayer.library.urls")),
]
