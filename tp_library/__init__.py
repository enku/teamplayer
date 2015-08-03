from django.apps import AppConfig
from django.utils.html import strip_tags
from haystack.utils import Highlighter as BaseHighlighter


class Highlighter(BaseHighlighter):
    """A haystack highlighter that does not truncate"""
    def highlight(self, text_block):
        self.text_block = strip_tags(text_block)
        text_len = len(self.text_block)
        highlight_locations = self.find_highlightable_words()

        return self.render_html(highlight_locations, 0, text_len)


class TPLibraryConfig(AppConfig):
    name = 'tp_library'
    label = 'tp_library'
    verbose_name = 'TeamPlayer Library'

default_app_config = 'tp_library.TPLibraryConfig'
