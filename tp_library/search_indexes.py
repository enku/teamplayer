from haystack import indexes

from tp_library.models import SongFile


class SongFileIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             model_attr='title',
                             null=True,
                             use_template=True)
    artist = indexes.CharField(null=True)
    album = indexes.CharField(null=True)
    genre = indexes.CharField(null=True)
    length = indexes.IntegerField(null=True)

    def get_model(self):
        return SongFile

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(artist__isnull=False,
                                               title__isnull=False)
