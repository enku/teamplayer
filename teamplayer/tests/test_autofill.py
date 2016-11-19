"""Tests for the autofill strategies"""
from django.test import TestCase

from teamplayer.lib.autofill import auto_fill_contiguous, auto_fill_random
from teamplayer.models import Player, Station
from tp_library.models import SongFile


class AutoFillTest:
    """Mixin for the autofill tests"""
    def setUp(self):
        parent = super()
        parent.setUp()

        self.dj_ango = Player.dj_ango()

        # let's fill the library with some songage
        for i in range(10):
            songfile = SongFile(
                filename='song{}.mp3'.format(i),
                artist='Artist {}'.format(i),
                title='Track {}'.format(i),
                album='Fake Album',
                genre='Unknown',
                length=300,
                filesize=3000,
                station_id=1,
                mimetype='audio/mp3',
                added_by=self.dj_ango,
            )
            songfile.save()


class RandomTest(AutoFillTest, TestCase):
    """tests for the random autofill strategy"""
    def test_empty_queryset_returns_empty_list(self):
        # given the empty queryset
        queryset = SongFile.objects.none()

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=10,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it returns an empty list
        self.assertEqual(result, [])

    def test_queryset_less_than_needed_returns_entire_queryset(self):
        # given the queryset
        queryset = SongFile.objects.all()[:5]

        # given the number of entries needed
        entries_needed = 30

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=entries_needed,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it returns the entire queryset
        all_songs = set(queryset)
        returned_songs = set(result)
        self.assertEqual(returned_songs, all_songs)

    def test_queryset_more_than_needed_returns_only_needed(self):
        # given the queryset
        queryset = SongFile.objects.all()

        # given the number of entries needed
        entries_needed = 5

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=entries_needed,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it only returns the number needed
        self.assertTrue(len(result), 5)

        # and they're all unique
        ids = set(song.pk for song in result)
        self.assertEqual(len(ids), 5)


class ContiguousTest(AutoFillTest, TestCase):
    """tests for the contiguous autofill strategy"""
    def test_empty_queryset_returns_empty_list(self):
        # given the empty queryset
        queryset = SongFile.objects.none()

        # when we call the contiguous strategy
        result = auto_fill_contiguous(
            entries_needed=10,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it returns an empty list
        self.assertEqual(result, [])

    def test_returns_songs_in_queryset_order(self):
        # given the queryset
        queryset = SongFile.objects.all()

        # when we call the contiguous strategy
        result = auto_fill_contiguous(
            entries_needed=4,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then the songs returned are in the same order as they are in the
        # queryset
        queryset_list = list(queryset)
        index = queryset_list.index(result[0])
        ordered_songs = queryset_list[index: index + 4]
        self.assertEqual(result, ordered_songs)

    def test_entries_needed_less_than_queryset_returns_full_set_ordered(self):
        # given the queryset
        queryset = SongFile.objects.all()[:5]

        # when we call the contiguous strategy needing more songs than are in
        # the queryset
        result = auto_fill_contiguous(
            entries_needed=20,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then we get back a list containing the entire queryset in order
        queryset_list = list(queryset)
        self.assertEqual(result, queryset_list)
