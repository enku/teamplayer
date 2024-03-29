"""Unit tests for teamplayer views."""

import json
import re
from unittest.mock import patch

import django.test
import django.urls

from teamplayer import views
from teamplayer.conf import settings
from teamplayer.models import Entry, Player, PlayLog, Station

from . import utils

RequestFactory = django.test.RequestFactory
SpinDoctor = utils.SpinDoctor
TestCase = django.test.TestCase
reverse = django.urls.reverse

SILENCE = utils.SILENCE


class HomePageView(TestCase):
    """Tests for the home page view (excluding song list)"""

    def setUp(self):
        # create a player
        self.player = Player.objects.create_player(username="test", password="test")
        self.client.login(username="test", password="test")
        self.url = reverse("home")

        patcher = patch("teamplayer.lib.mpc.MPC")
        self.addCleanup(patcher.stop)
        mpc = patcher.start()
        mpc.return_value.http_port = 8002
        mpc.return_value.currently_playing.return_value = {
            "dj": "DJ Skipp Traxx",
            "artist": "Prince",
            "title": "Purple Rain",
            "total_time": 99,
            "remaining_time": 12,
            "station_id": 1,
            "artist_image": "/artist/Prince/image",
        }
        self.mpc = mpc

        self.client.get(self.url)

    def test_home(self):
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_dj_name_appears(self):
        self.player.dj_name = "Skipp Traxx"
        self.player.save()
        response = self.client.get(self.url, follow=True)
        self.assertContains(response, "Skipp Traxx")

    @patch("teamplayer.lib.websocket.IPCHandler.send_message")
    def test_set_djname(self, mock):
        """Test that we can set the dj name in the view"""
        # This doesn't test the home page view per-se but it's an AJAX view
        # accessible via the home page
        url = reverse("change_dj_name")
        response = self.client.post(url, {"dj_name": "Liquid X"})
        self.assertEqual(response.status_code, 204)
        player = Player.objects.get(user__username="test")
        self.assertEqual(player.dj_name, "Liquid X")
        mock.assert_called_with(
            message_type="dj_name_change",
            data={"dj_name": "Liquid X", "previous_dj_name": "", "user_id": player.pk},
        )

    @patch("teamplayer.views.MPC")
    def test_song_display(self, mpc):
        """Test that the currently playing area is working"""
        mpc.return_value = self.mpc.return_value
        url = reverse("currently_playing")
        response = self.client.get(url)
        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data["dj"], "DJ Skipp Traxx")
        self.assertEqual(data["artist"], "Prince")
        self.assertEqual(data["title"], "Purple Rain")
        self.assertEqual(data["total_time"], 99)
        self.assertEqual(data["remaining_time"], 12)
        self.assertEqual(
            data["artist_image"], reverse("artist_image", kwargs={"artist": "Prince"})
        )

    @patch("teamplayer.views.MPC.currently_playing")
    def test_currently_playing(self, mock):
        mock.return_value = {
            "dj": "DJ Skipp Traxx",
            "artist": "Prince",
            "title": "Purple Rain",
            "total_time": 99,
            "remaining_time": 12,
            "station_id": 1,
            "artist_image": "/artist/Prince/image",
        }

        url = reverse("currently_playing")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data["dj"], "DJ Skipp Traxx")
        self.assertEqual(data["artist"], "Prince")
        self.assertEqual(data["title"], "Purple Rain")

    @patch("teamplayer.views.MPC.currently_playing")
    def test_going_back_to_station(self, mock):
        """Show that we don't get infinite redirects when re-getting
        the station page"""
        response = self.client.get(self.url, follow=True)
        redirect_chain = response.redirect_chain
        self.assertLessEqual(len(redirect_chain), 1)


class ShowQueueView(TestCase):
    """Tests the teamplayer.views.show_queue view"""

    def setUp(self):
        # create a player
        self.player = Player.objects.create_player(username="test", password="test")
        self.client.login(username="test", password="test")
        self.url = reverse("show_queue")

    def test_empty_queue(self):
        """Test that we get the appropriate info when we have an empty
        queue"""
        response = self.client.get(self.url)
        self.assertContains(response, "[]")

    def test_queue_with_songs(self):
        """Test that songs added show up in the list"""
        spin = SpinDoctor()
        spin.create_song_for(self.player, "Prince", "Purple Rain")
        response = self.client.get(self.url)
        self.assertContains(response, "Prince")
        self.assertContains(response, "Purple Rain")

    def test_queue_reordering(self):
        """Test that after re-ordering the queue it shows up in the new
        order Also tests that the reorder_queue view works"""
        spin = SpinDoctor()
        spin.create_song_for(self.player, "Prince", "Purple Rain")
        spin.create_song_for(self.player, "Metallica", "One")
        spin.create_song_for(self.player, "Arcade Fire", "Rococo")

        player = Player.objects.get(user__username="test")
        current_order = [x.id for x in player.queue.entry_set.all()]
        new_order = list(reversed(current_order))
        new_order_str = ",".join([str(i) for i in new_order])
        response = self.client.post(
            reverse("reorder_queue"), new_order_str, content_type="text/plain"
        )

        returned_order = json.loads(response.content.decode("utf-8"))
        self.assertEqual(returned_order, new_order)
        response = self.client.get(self.url)
        match = re.search(
            "Arcade Fire.*Metallica.*Prince",
            response.content.decode("utf-8").replace("\n", " "),
        )
        self.assertNotEqual(match, None)

    @patch("teamplayer.lib.websocket.IPCHandler.send_message")
    def test_remove_from_queue(self, mock):
        """Tests that removing a song from the queue makes it no longer
        show in the list"""
        spin = SpinDoctor()
        spin.create_song_for(self.player, "Prince", "Purple Rain")

        response = self.client.get(self.url)
        self.assertContains(response, "Purple Rain")
        song_id = self.player.queue.entry_set.all()[0].id

        response = self.client.delete(reverse("show_entry", args=(song_id,)))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Purple Rain")
        self.assertContains(response, "[]")

    @patch("teamplayer.lib.songs.get_similar_artists")
    def test_queue_after_song_plays(self, mock_call):
        """Test that song is removed from songlist when it plays"""
        spin = SpinDoctor()
        spin.create_song_for(self.player, "Prince", "Purple Rain")
        response = self.client.get(self.url)
        self.assertContains(response, "Prince")
        self.assertContains(response, "Purple Rain")

        spin.next()
        response = self.client.get(self.url)
        self.assertNotContains(response, "Prince")
        self.assertNotContains(response, "Purple Rain")


class ClearQueueView(TestCase):
    """tests for the teamplayer.views.clear_queue view"""

    def setUp(self):
        self.player = Player.objects.create_player(username="test", password="test")
        self.client.login(username="test", password="test")
        self.url = reverse("show_queue")

        # create a player station
        self.station = Station.objects.create_station(
            creator=self.player, name="test_station"
        )

    def test_clears_queue(self):
        # given the player's songs
        song = SILENCE
        queue = self.player.queue
        station = Station.main_station()

        for i in range(3):
            Entry.objects.create(song=song, queue=queue, station=station)

        queue_count = Entry.objects.filter(queue=queue).count()
        self.assertEqual(queue_count, 3)

        # when we POST to the clear queue view
        url = reverse("clear_queue")
        with patch("teamplayer.views.IPCHandler") as IPCHandler:
            response = self.client.post(url)

        # then it clears the queue
        self.assertEqual(response.status_code, 204)
        queue_count = Entry.objects.filter(queue=queue).count()
        self.assertEqual(queue_count, 0)

        # and messages are sent
        self.assertEqual(IPCHandler.send_message.call_count, 3)

    def test_only_clears_songs_for_station(self):
        # given the player's songs in different stations
        song = SILENCE
        queue = self.player.queue
        main_station = Station.main_station()
        my_station = self.station

        for i in range(3):
            Entry.objects.create(song=song, queue=queue, station=main_station)
        Entry.objects.create(song=song, queue=queue, station=my_station)

        # when we POST to the clear queue view for the main station
        url = reverse("clear_queue")
        with patch("teamplayer.views.IPCHandler"):
            self.client.post(url)

        # then it clears only the songs from the main station
        entries = Entry.objects.filter(queue=queue)
        self.assertEqual(entries.count(), 1)
        my_song = entries.get()
        self.assertEqual(my_song.station, my_station)


class AddUserView(TestCase):
    """Test the add_user view"""

    def setUp(self):
        self.form_data = {
            "username": "test",
            "password1": "password",
            "password2": "password",
        }

    def test_get_returns_200(self):
        response = self.client.get(reverse("registration"))
        self.assertEqual(response.status_code, 200)

    @patch("teamplayer.lib.websocket.IPCHandler.send_message")
    def test_can_add_user(self, mock):
        self.client.post(reverse("registration"), self.form_data)

        # check that the user exists
        test_player = Player.objects.get(user__username=self.form_data["username"])

        # check that the user has a player and a queue
        self.assertTrue(test_player)
        self.assertTrue(hasattr(test_player, "queue"))

    @patch("teamplayer.lib.websocket.IPCHandler.send_message")
    def test_user_already_exists(self, mock):
        form_data = self.form_data

        # add user
        self.client.post(reverse("registration"), form_data)

        # now add again
        response = self.client.post(reverse("registration"), form_data, follow=True)
        self.assertContains(response, "already exists")


class EditStationView(TestCase):
    """Test the edit_station view"""

    url = reverse("edit_station")

    def setUp(self):
        # create a player
        self.player = Player.objects.create_player(username="test", password="test")
        self.client.login(username="test", password="test")

        patcher = patch("teamplayer.lib.mpc.MPC")
        self.addCleanup(patcher.stop)
        mpc = patcher.start()
        mpc.return_value.http_port = 8002
        mpc.return_value.currently_playing.return_value = {}

    def test_invalid_input(self):
        # given the edit_station view url
        url = self.url

        # given the invalid POST input
        post_data = {"action": "rename", "station_id": 1}

        # when we POST it to the url
        response = self.client.post(url, data=post_data)

        # then we get a Bad Request response
        self.assertEqual(response.status_code, 400)

        # and a json object telling us our errors
        self.assertEqual(response["content-type"], "application/json")
        expected = {"name": ["This field is required."]}
        self.assertEqual(json.loads(response.content.decode()), expected)

    def test_http_get(self):
        # given the edit_station view url
        url = self.url

        # when we http GET on the url
        response = self.client.get(url)
        # then we get an method not allowed response
        self.assertEqual(response.status_code, 405)

    def test_station_does_not_exist(self):
        # given the edit_station view url
        url = self.url

        # given the user station that is subsequently removed
        station = Station.create_station("Test", self.player)
        station_id = station.pk
        station.delete()

        # when the user goes to the remove station url
        post_data = {
            "name": "Rename my station",
            "action": "rename",
            "station_id": station_id,
        }
        response = self.client.post(url, data=post_data)

        # then we get a 404
        self.assertEqual(response.status_code, 404)

    def test_not_my_station(self):
        # given the edit_station view url
        url = self.url

        # given the station that does not belong to him
        station_id = Station.main_station().pk

        # when the user goes to the remove station url
        post_data = {
            "name": "Hijacked Station",
            "action": "rename",
            "station_id": station_id,
        }
        response = self.client.post(url, data=post_data)

        # then we get a 404 (although we should get a 403)
        self.assertEqual(response.status_code, 404)

    def test_station_rename(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user posts and edit to rename the station
        post_data = {
            "action": "rename",
            "station_id": station.id,
            "name": "The Best Station",
        }
        with patch("teamplayer.views.IPCHandler.send_message"):
            response = self.client.post(url, data=post_data)

        # then we get a 200 response
        self.assertEqual(response.status_code, 200)

        # and the station is renamed
        station = Station.objects.get(id=station.id)
        self.assertEqual(station.name, "The Best Station")

    def test_station_rename_ipc(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user posts and edit to rename the station
        post_data = {
            "action": "rename",
            "station_id": station.id,
            "name": "The Best Station",
        }
        with patch("teamplayer.views.IPCHandler.send_message") as send_message:
            self.client.post(url, data=post_data)

        # then an IPC message is sent alerting that the station was renamed
        send_message.assert_called_with(
            "station_rename", [station.id, "The Best Station"]
        )

    def test_station_remove(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user edits the station for removal
        post_data = {"action": "remove", "station_id": station.id, "name": "Test"}
        with patch("teamplayer.views.IPCHandler.send_message"):
            response = self.client.post(url, data=post_data)

        # then we get a 200 response
        self.assertEqual(response.status_code, 200)

        exists = Station.objects.filter(id=station.id).exists()
        self.assertFalse(exists)

    def test_station_remove_actually_disables(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user edits the station for removal
        post_data = {"action": "remove", "station_id": station.id, "name": "Test"}
        with patch("teamplayer.views.IPCHandler.send_message"):
            self.client.post(url, data=post_data)

        # Then the station gets disabled
        station = Station.objects.disabled.get(id=station.id)
        self.assertFalse(station.enabled)

    def test_station_remove_from_station(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user is listening to that station
        self.client.get(reverse("station", args=[station.id]))
        assert self.client.session["station_id"] == station.id

        # and the user edits the station for removal
        post_data = {"action": "remove", "station_id": station.id, "name": "Test"}
        with patch("teamplayer.views.IPCHandler.send_message"):
            self.client.post(url, data=post_data)

        # then the user's station change to the main station
        main_station = Station.main_station()
        self.assertEqual(self.client.session["station_id"], main_station.id)

    def test_station_remove_ipc(self):
        # given the edit_station view url
        url = self.url

        # given the user's station
        station = Station.create_station("Test", self.player)

        # when the user edits the station for removal
        post_data = {"action": "remove", "station_id": station.id, "name": "Test"}
        with patch("teamplayer.views.IPCHandler.send_message") as send_message:
            self.client.post(url, data=post_data)

        # then an IPC message is sent alerting that the station was removed
        send_message.assert_called_with("station_delete", station.id)


class AboutView(TestCase):
    """tests for the /about view"""

    def test_with_empty_playlog(self):
        # given the empty playlog
        assert PlayLog.objects.count() == 0

        # when we go to the about view
        url = reverse("about")
        with patch("teamplayer.lib.mpc.MPC.get_version"):
            response = self.client.get(url, HTTP_USER_AGENT="Django Test")

        # then it shows DJ Ango hasn't played any tracks
        self.assertContains(response, "DJ Ango hasn't played any tracks")


class RegistrationTest(TestCase):
    def test_no_player(self):
        """Show that we don't get the audio player in the registration view."""
        # when we access the registration page
        response = self.client.get(reverse("registration"))

        # Then it doesn't show up.
        self.assertNotContains(response, "audioplayer")

    def test_no_stations(self):
        """Show that we don't get the station links in the view."""
        # when we access the registration page
        response = self.client.get(reverse("register"))

        # Then it doesn't show up.
        self.assertNotContains(response, "next station")


class JSObjectTest(TestCase):
    """Tests for the js_object() view"""

    view = "js_object"

    def setUp(self):
        # create a player
        self.player = Player.objects.create_player(username="test", password="test")
        self.client.login(username="test", password="test")

    def test_view(self):
        # Given the js_object url
        url = reverse(self.view)

        # When we view it
        response = self.client.get(url)

        # Then we get a big javascript object
        self.assertContains(response, "var TeamPlayer =")


class GetMPDUrl(TestCase):
    """Tests for the get_mpd_url() helper function"""

    def setUp(self):
        self.player = Player.objects.create_player(username="test", password="test")

        # create a player station
        self.station = Station.objects.create_station(
            creator=self.player, name="test_station"
        )

    def test(self):
        request = RequestFactory().get(f"/channel/{self.station.id}/")
        request.station = self.station

        url = views.get_mpd_url(request, self.station)

        server = request.META["SERVER_NAME"]
        port = settings.HTTP_PORT

        self.assertEqual(url, f"http://{server}:{port + self.station.id}/mpd.mp3")
