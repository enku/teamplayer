import logging
import os

from django.core.management.base import BaseCommand
from mutagen import File

from teamplayer.lib import remove_pedantic
from teamplayer.models import DJ_ANGO, Station
from tp_library.models import SongFile

# Because Python 3 sucks:
os.environ.setdefault('LANG', 'en_US.UTF-8')

logger = logging.getLogger('teamplayer.library.walk')


class Command(BaseCommand):
    help = 'Walk specified directory and update the database'

    option_list = BaseCommand.option_list

    def handle(self, *args, **options):
        self.created = 0
        self.skipped = 0
        self.errors = 0
        self.station = Station.main_station()

        for arg in args:
            path = os.path.realpath(arg)
            for tup in os.walk(path):
                self._handle_files(*tup)

        logger.info('added:   %s', self.created)
        logger.info('errors:  %s', self.errors)
        logger.info('skipped: %s', self.skipped)

    def _handle_files(self, dirpath, dirnames, filenames):
        player = DJ_ANGO
        station_id = self.station.pk

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)

            # First we need to make sure that the fullpath is encodable, because
            # if it's not then we can't even save it in the database
            try:
                fullpath.encode('utf-8')
            except UnicodeEncodeError:
                logger.exception('Filename cannot be used')
                self.errors += 1
                continue

            try:
                metadata = File(fullpath, easy=True)
            except IOError:
                logger.exception('Error adding %s to library', fullpath,
                                 exc_info=True)
                self.errors += 1
                continue
            if not metadata:
                continue

            songfile, created = SongFile.metadata_get_or_create(
                fullpath,
                metadata,
                player,
                station_id
            )
            if created:
                logger.info('added "%s" by %s', songfile.title, songfile.artist)
                self.created += 1
            else:
                self.skipped += 1


remove_pedantic()
