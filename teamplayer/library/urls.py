from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^search/", views.song_search, name="library_search"),
    re_path(r"^add_to_queue", views.add_to_queue, name="library_add_to_queue"),
]
