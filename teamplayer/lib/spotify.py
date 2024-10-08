"""Library for Spotify integration"""

import base64
import time
from typing import Any, TypedDict

import requests

from teamplayer.conf import settings


class TokenRefreshError(Exception):
    pass


class Token(TypedDict):
    _granted: float
    access_token: str | None
    token_type: str
    expires_in: float


class Auth:
    token: Token = {
        "_granted": time.mktime(time.gmtime()),
        "access_token": None,
        "token_type": "Bearer",
        "expires_in": 0,
    }

    token_url = "https://accounts.spotify.com/api/token"
    client_id = settings.SPOTIFY_CLIENT_ID
    client_secret = settings.SPOTIFY_CLIENT_SECRET

    @classmethod
    def token_expired(cls) -> bool:
        elapsed = time.mktime(time.gmtime()) - cls.token["_granted"]

        return elapsed >= cls.token["expires_in"]

    @classmethod
    def refresh_token(cls) -> Token:
        creds = f"{cls.client_id}:{cls.client_secret}"
        encoded_creds = base64.b64encode(creds.encode("ascii")).decode("ascii")
        headers = {"Authorization": f"Basic {encoded_creds}"}
        data = {"grant_type": "client_credentials"}

        response = requests.post(cls.token_url, data=data, headers=headers)

        if response.status_code != 200:
            raise TokenRefreshError(response.content)

        token: Token = response.json()
        timestamp = time.strptime(response.headers["date"], "%a, %d %b %Y %H:%M:%S GMT")
        token["_granted"] = time.mktime(timestamp)

        cls.token = token

        return token

    @classmethod
    def check_expiration(cls) -> None:
        if cls.token_expired():
            cls.refresh_token()

    @classmethod
    def get_auth_header(cls) -> dict[str, str]:
        cls.check_expiration()
        return {"Authorization": f"Bearer {cls.token['access_token']}"}


def search(query_type: str, query: str) -> dict[str, Any]:
    response = requests.get(
        "https://api.spotify.com/v1/search",
        {"q": query, "type": query_type},
        headers=Auth.get_auth_header(),
    )

    search_result: dict[str, Any] = response.json()
    return search_result
