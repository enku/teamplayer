import os

from django.core.exceptions import ValidationError
from django.db import models

from teamplayer import logger
from teamplayer.lib import first_or_none, songs
from teamplayer.models import Player


class SongFile(models.Model):
    objects = models.Manager()

    filename = models.TextField(unique=True)
    filesize = models.IntegerField()
    mimetype = models.TextField()
    artist = models.TextField()
    title = models.TextField()
    album = models.TextField()
    length = models.IntegerField(null=True)  # in seconds
    genre = models.TextField(null=True, blank=True)
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
            genre = first_or_none(metadata, 'genre') or None
            length = metadata.info.length

            if length:
                length = int(length)
            else:
                length = None

        except Exception as error:
            logger.error('Error getting metadata for %s: %s', filename, error)
            raise

        # see if we already have a file with said metadata
        try:
            return (cls.objects.get(artist__iexact=artist,
                                    title__iexact=title,
                                    album__iexact=album),
                    False)
        except cls.DoesNotExist:
            pass

        songfile = cls(
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
        songfile.full_clean()  # callers should trap me
        songfile.save()

        return (songfile, True)

    def image(self):
        """Return artist image url"""
        return songs.get_image_url_for(self.artist)

    def __str__(self):
        if self.title:
            return '"{0}" by {1}'.format(self.title, self.artist)
        return self.filename

    def clean(self):
        if self.artist.lower() in ('', 'unknown'):
            raise ValidationError('Invalid artist: %s' % self.artist)

        self.genre = self.genre or None
        self.length = self.length or None
