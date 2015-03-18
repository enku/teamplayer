from .models import Player, Queue, Station


class TeamPlayerMiddleware(object):
    """Special middleware for TeamPlayer

    This middleware requires the auth and session middlewares, so be certain to
    place it after.
    """
    def process_request(self, request):
        """Add a "player" attribute to the request object."""
        if hasattr(request, 'user') and request.user.is_authenticated():
            user = request.user
            try:
                player = Player.objects.get(user=user)
            except Player.DoesNotExist:
                queue = Queue.objects.create()
                player = Player.objects.create(
                    user=user, queue=queue, dj_name='')
            request.player = player

        # station
        main_station = Station.main_station()
        request.station = None
        if 'station_id' in request.session:
            try:
                station_id = request.session['station_id']
                station = Station.objects.get(pk=station_id)
                request.station = station
            except Station.DoesNotExist:
                pass

        if not request.station:
            # put 'em on the main station
            request.session['station_id'] = main_station.pk
            request.station = main_station

        return None
