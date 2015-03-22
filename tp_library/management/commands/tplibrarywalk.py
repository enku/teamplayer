import os
from optparse import make_option

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from mutagen import File

from teamplayer import logger
from teamplayer.lib import attempt_file_rename, remove_pedantic
from teamplayer.models import Player, Station
from tp_library.models import SongFile

# Because Python 3 sucks:
os.environ.setdefault('LANG', 'en_US.UTF-8')


class Command(BaseCommand):
    args = '[--rename] <dir>'
    help = 'Walk specified directory and update the database'

    option_list = BaseCommand.option_list + (
        make_option('--rename',
                    action='store_true',
                    dest='rename',
                    default=False,
                    help='Attempt to rename non-utf-8 filenames'),
    )

    def handle(self, *args, **options):
        self.options = options
        self.created = 0
        self.skipped = 0
        self.errors = 0
        self.renamed = 0
        self.station = Station.main_station()
        self.dj_ango = Player.dj_ango()

        for arg in args:
            path = os.path.realpath(arg)
            for tup in os.walk(path):
                self._handle_files(*tup)

        logger.info('added:   %s', self.created)
        if self.renamed:
            logger.info('renamed: %s', self.renamed)
        logger.info('errors:  %s', self.errors)
        logger.info('skipped: %s', self.skipped)

    def _rename_file(self, fullpath):
        newname = attempt_file_rename(fullpath)
        if newname:
            try:
                os.rename(fullpath, newname)
            except OSError:
                logger.exception('Error renaming')
                return None
            msg = '%s has been renamed'
            logger.info(msg, newname)
            return newname
        else:
            return None

    def _handle_files(self, dirpath, dirnames, filenames):
        player = self.dj_ango
        station_id = self.station.pk

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)

            # First we need to make sure that the fullpath is encodable, because
            # if it's not then we can't even save it in the database
            try:
                fullpath.encode('utf-8')
            except UnicodeEncodeError:
                renamed = False
                if self.options['rename']:
                    newname = self._rename_file(fullpath)
                    if newname:
                        fullpath = newname
                        self.renamed += 1
                        renamed = True
                if not renamed:
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

            try:
                songfile, created = SongFile.metadata_get_or_create(
                    fullpath,
                    metadata,
                    player,
                    station_id
                )
            except ValidationError:
                self.errors += 1
                continue

            if created:
                logger.info('added "%s" by %s', songfile.title, songfile.artist)
                self.created += 1
            else:
                self.skipped += 1


remove_pedantic()
