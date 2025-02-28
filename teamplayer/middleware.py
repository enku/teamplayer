# mypy: disable-error-code="attr-defined"
from typing import Callable, TypeAlias

from django.http import HttpRequest, HttpResponse

from .models import Player, Queue, Station

MiddlewareCallable: TypeAlias = Callable[[HttpRequest], HttpResponse]


def TeamPlayerMiddleware(  # pylint: disable=invalid-name
    get_response: Callable[[HttpRequest], HttpResponse],
) -> MiddlewareCallable:
    """Special middleware for TeamPlayer

    This middleware requires the auth and session middlewares, so be certain to
    place it after.
    """

    def call(request: HttpRequest) -> HttpResponse:
        """Add a "player" attribute to the request object."""
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
            try:
                player = Player.objects.get(user=user)
            except Player.DoesNotExist:
                queue = Queue.objects.create()
                player = Player.objects.create(user=user, queue=queue, dj_name="")
            request.player = player

        # station
        main_station = Station.main_station()
        request.station = None
        session = request.session
        if station_id := session.get("station_id"):
            try:
                request.station = Station.objects.get(pk=station_id)
            except Station.DoesNotExist:
                pass

        if not request.station:
            # put 'em on the main station
            session["station_id"] = main_station.pk
            request.station = main_station

        return get_response(request)

    return call
