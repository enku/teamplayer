import os
from dataclasses import dataclass
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandParser
from mutagen import File  # type: ignore[attr-defined]

from teamplayer import logger
from teamplayer.lib import attempt_file_rename
from teamplayer.models import LibraryItem, Player, Station

os.environ.setdefault("LANG", "en_US.UTF-8")


@dataclass
class Stats:
    created: int = 0
    skipped: int = 0
    errors: int = 0
    renamed: int = 0


class Command(BaseCommand):
    help = "Walk specified directory and update the database"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--rename",
            action="store_true",
            dest="rename",
            default=False,
            help="Attempt to rename non-utf-8 filenames",
        )
        parser.add_argument("dir", nargs="+", help="Directory to walk")

    def handle(self, *args: Any, **options: Any) -> None:
        self.station = Station.main_station()
        self.dj_ango = Player.dj_ango()
        stats = Stats()

        for directory in options["dir"]:
            path = os.path.realpath(directory)
            for tup in os.walk(path):
                self._handle_files(*tup, stats, options["rename"])

        logger.info("added:   %s", stats.created)
        if stats.renamed:
            logger.info("renamed: %s", stats.renamed)
        logger.info("errors:  %s", stats.errors)
        logger.info("skipped: %s", stats.skipped)

    def _rename_file(self, fullpath: str) -> str | None:
        if newname := attempt_file_rename(fullpath):
            try:
                os.rename(fullpath, newname)
            except OSError:
                logger.exception("Error renaming")
                return None
            msg = "%s has been renamed"
            logger.info(msg, newname)
            return newname
        return None

    def _handle_files(
        self,
        dirpath: str,
        _dirnames: Any,
        filenames: Iterable[str],
        stats: Stats,
        rename: bool,
    ) -> None:
        player = self.dj_ango
        station_id = self.station.pk

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)

            # First we need to make sure that the fullpath is encodable,
            # because if it's not then we can't even save it in the
            # database
            try:
                fullpath.encode("utf-8")
            except UnicodeEncodeError:
                renamed = False
                if rename:
                    newname = self._rename_file(fullpath)
                    if newname:
                        fullpath = newname
                        stats.renamed += 1
                        renamed = True
                if not renamed:
                    logger.exception("Filename cannot be used")
                    stats.errors += 1
                    continue

            try:
                metadata = File(fullpath, easy=True)
            except Exception:
                logger.exception("Error adding %s to library", fullpath, exc_info=True)
                stats.errors += 1
                continue
            if not metadata:
                continue

            try:
                songfile, created = LibraryItem.metadata_get_or_create(
                    fullpath, metadata, player, station_id
                )
            except ValidationError:
                stats.errors += 1
                continue

            if created:
                logger.info('added "%s" by %s', songfile.title, songfile.artist)
                stats.created += 1
            else:
                stats.skipped += 1
