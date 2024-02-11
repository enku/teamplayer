"""Tests for the lib.spotify module"""

import json
import time
from unittest import mock

from django.test import TestCase

from teamplayer.lib import spotify

from . import utils


class SpotifyTestCase(TestCase):
    spotify.Auth.token = {
        "_granted": 1600658205.0,
        "access_token": None,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    spotify.Auth.token_url = "https://accounts.spotify.invalid/api/token"
    spotify.Auth.client_id = "SPOTIFY_CLIENT_ID"
    spotify.Auth.client_secret = "SPOTIFY_CLIENT_SECRET"


class AuthTestCase(SpotifyTestCase):
    """tests for the Auth class/singleton"""

    def test_token_expired_not_expired(self):
        now_s = 1600658205.0
        now_struct_time = time.gmtime(now_s)

        with mock.patch("teamplayer.lib.spotify.time.gmtime") as gmtime:
            gmtime.return_value = now_struct_time
            spotify.Auth.token["expires_in"] = 3600
            spotify.Auth.token["_granted"] = now_s - 1800
            expired = spotify.Auth.token_expired()

        self.assertFalse(expired)

    def test_token_expired_is_expired(self):
        now_s = 1600658205.0
        now_struct_time = time.gmtime(now_s)

        with mock.patch("teamplayer.lib.spotify.time.gmtime") as gmtime:
            gmtime.return_value = now_struct_time
            spotify.Auth.token["expires_in"] = 3600
            spotify.Auth.token["_granted"] = now_s - 3600 - 60
            expired = spotify.Auth.token_expired()

        self.assertTrue(expired)

    def test_refresh_token(self):
        requests_post = "teamplayer.lib.spotify.requests.post"
        response_json = {
            "access_token": "BQDNZo...1qvy3gS",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "",
        }
        response_headers = {
            "date": "Mon, 21 Sep 2020 02:14:46 GMT",
            "content-type": "application/json",
        }

        with mock.patch(requests_post) as mock_post:
            response = mock_post.return_value
            response.status_code = 200
            response.headers = response_headers
            response.json.return_value = response_json
            token = spotify.Auth.refresh_token()

        expected = response_json.copy()
        expected["_granted"] = 1600654486.0
        self.assertEqual(token, expected)
        self.assertIs(spotify.Auth.token, token)

    def test_refresh_token_non_200_response(self):
        requests_post = "teamplayer.lib.spotify.requests.post"

        with mock.patch(requests_post) as mock_post:
            with self.assertRaises(spotify.TokenRefreshError) as context:
                response = mock_post.return_value
                response.status_code = 400
                response.content = b"foobar"
                spotify.Auth.refresh_token()

            exception = context.exception
            self.assertEqual(exception.args, (b"foobar",))

    def test_check_expiration_not_expired(self):
        with mock.patch("teamplayer.lib.spotify.Auth.token_expired") as token_expired:
            token_expired.return_value = False

            with mock.patch(
                "teamplayer.lib.spotify.Auth.refresh_token"
            ) as refresh_token:
                spotify.Auth.check_expiration()

                self.assertFalse(refresh_token.called)

    def test_check_expiration_expired(self):
        with mock.patch("teamplayer.lib.spotify.Auth.token_expired") as token_expired:
            token_expired.return_value = True

            with mock.patch(
                "teamplayer.lib.spotify.Auth.refresh_token"
            ) as refresh_token:
                spotify.Auth.check_expiration()

                self.assertTrue(refresh_token.called)

    def test_get_auth_header(self):
        spotify.Auth.token["access_token"] = "BQDNZo...1qvy3gS"

        with mock.patch("teamplayer.lib.spotify.Auth.token_expired") as token_expired:
            token_expired.return_value = False
            header = spotify.Auth.get_auth_header()

        expected = {"Authorization": "Bearer BQDNZo...1qvy3gS"}
        self.assertEqual(header, expected)


class SearchTestCase(SpotifyTestCase):
    """tests for spotify.search()"""

    def test(self):
        with utils.getdata("spotify_artist_search.json", "rb") as data:
            json_response = data.read()

        artist = "Alejandro Fernández"
        headers = {"Authorization": "Bearer BQDNZo...1qvy3gS"}

        with mock.patch("teamplayer.lib.spotify.requests.get") as mock_get:
            response = mock_get.return_value
            response.json.return_value = json.loads(json_response)
            with mock.patch("teamplayer.lib.spotify.Auth.get_auth_header") as g_a_h:
                g_a_h.return_value = headers
                result = spotify.search("artist", artist)

        expected = json.loads(json_response)
        self.assertEqual(result, expected)

        mock_get.assert_called_with(
            "https://api.spotify.com/v1/search",
            {"q": artist, "type": "artist"},
            headers=headers,
        )
