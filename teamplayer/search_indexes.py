from haystack import indexes

from .models import LibraryItem


class LibraryItemIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    artist = indexes.CharField(model_attr="artist")
    title = indexes.CharField(model_attr="title")
    album = indexes.CharField(model_attr="album")
    genre = indexes.CharField(model_attr="genre", null=True)

    def get_model(self) -> type[LibraryItem]:
        return LibraryItem
