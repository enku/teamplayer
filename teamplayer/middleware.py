
class TeamPlayerMiddleware(object):
    """Special middleware for TeamPlayer"""
    def process_request(self, request):
        """Add a "player" attribute to the request object."""
        if hasattr(request, 'user') and hasattr(request.user, 'player'):
            request.player = request.user.player
        return None
