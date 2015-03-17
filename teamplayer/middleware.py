from .models import Player, Queue


class TeamPlayerMiddleware(object):
    """Special middleware for TeamPlayer"""
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

        return None
