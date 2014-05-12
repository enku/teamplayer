import logging
import os

from teamplayer.lib import first_or_none, songs
from teamplayer.models import Player

from django.core.urlresolvers import reverse
from django.db import models

LOGGER = logging.getLogger('teamplayer.library')


class SongFile(models.Model):
    objects = models.Manager()

    filename = models.TextField(unique=True)
    filesize = models.IntegerField()
    mimetype = models.TextField()
    artist = models.TextField()
    title = models.TextField()
    album = models.TextField()
    length = models.IntegerField(null=True)  # in seconds
    genre = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)
    station_id = models.IntegerField()
    added_by = models.ForeignKey(Player, related_name='library_songs')

    class Meta:
        unique_together = (('artist', 'title', 'album'),)

    def similar_artists(self):
        return songs.get_similar_artists(self.artist) if self.artist else None

    def exists(self):
        return os.path.exists(self.filename)

    @classmethod
    def metadata_get_or_create(cls, filename, metadata, contributer, st_id):
        try:
            artist = first_or_none(metadata, 'artist') or ''
            title = first_or_none(metadata, 'title') or ''
            album = first_or_none(metadata, 'album') or ''
            genre = first_or_none(metadata, 'genre') or ''
            length = metadata.info.length

            if length:
                length = int(length)
            else:
                length = None

        except Exception as error:
            LOGGER.error('Error getting metadata for %s: %s', filename, error)
            raise

        # see if we already have a file with said metadata
        try:
            return (cls.objects.get(artist__iexact=artist,
                                    title__iexact=title,
                                    album__iexact=album),
                    False)
        except cls.DoesNotExist:
            pass

        songfile = cls.objects.create(
            filename=filename,
            filesize=os.stat(filename).st_size,
            mimetype=metadata.mime[0],
            artist=artist,
            title=title,
            album=album,
            length=length,
            genre=genre,
            station_id=st_id,
            added_by=contributer
        )

        return (songfile, True)

    def image(self):
        """Return artist image url"""
        return songs.get_image_url_for(self.artist)

    def __str__(self):
        if self.title:
            return u'"{0}" by {1}'.format(self.title, self.artist)
        return self.filename

    def get_absolute_url(self):
        return reverse('tp_library.views.get_song', args=[str(self.pk)])
