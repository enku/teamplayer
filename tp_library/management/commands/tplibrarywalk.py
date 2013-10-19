import os

from mutagen import File
from mutagen.mp3 import HeaderNotFoundError

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from teamplayer.lib import remove_pedantic
from teamplayer.models import Station
from tp_library.models import SongFile


class Command(BaseCommand):
    help = 'Walk specified directory and update the database'

    option_list = BaseCommand.option_list

    def handle(self, *args, **options):
        self.created = 0
        self.station = Station.main_station()
        self.dj_ango = User.dj_ango()

        for arg in args:
            path = os.path.realpath(arg)
            os.path.walk(path, self._handle_dir, None)

        print self.created

    def _handle_dir(self, arg, dirname, fnames):
        user = self.dj_ango
        station_id = self.station.pk

        for fname in fnames:
            fullpath = os.path.join(dirname, fname)
            if not os.path.isfile(fullpath):
                continue

            try:
                metadata = File(fullpath, easy=True)
            except HeaderNotFoundError:
                continue
            if not metadata:
                continue

            songfile, created = SongFile.metadata_get_or_create(
                fullpath,
                metadata,
                user,
                station_id
            )
            if created:
                self.created += 1


remove_pedantic()
