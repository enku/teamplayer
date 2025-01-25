from django.urls import path

from . import views

urlpatterns = [
    path("search/", views.song_search, name="library_search"),
    path("add_to_queue", views.add_to_queue, name="library_add_to_queue"),
]
