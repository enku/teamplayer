import os

from mutagenx import File
from mutagenx.mp3 import HeaderNotFoundError

from teamplayer.lib import remove_pedantic
from teamplayer.models import Player, Station
from tp_library.models import SongFile

from django.core.management.base import BaseCommand

# Because Python 3 sucks:
os.environ.setdefault('LANG', 'en_US.UTF-8')


class Command(BaseCommand):
    help = 'Walk specified directory and update the database'

    option_list = BaseCommand.option_list

    def handle(self, *args, **options):
        self.created = 0
        self.station = Station.main_station()
        self.dj_ango = Player.dj_ango()

        for arg in args:
            path = os.path.realpath(arg)
            for tup in os.walk(path):
                self._handle_files(*tup)

        print(self.created)

    def _handle_files(self, dirpath, dirnames, filenames):
        user = self.dj_ango
        station_id = self.station.pk

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)

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
