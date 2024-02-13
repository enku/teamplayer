from typing import cast

from django.utils.html import strip_tags
from haystack.utils import Highlighter as BaseHighlighter


class Highlighter(BaseHighlighter):  # type: ignore
    """A haystack highlighter that does not truncate"""

    def highlight(self, text_block: str) -> str:
        self.text_block = strip_tags(text_block)
        text_len = len(self.text_block)
        highlight_locations = self.find_highlightable_words()

        return cast(str, self.render_html(highlight_locations, 0, text_len))
