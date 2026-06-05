import re

class BidiTermFormatter:
    _TERM = re.compile(r"\[\[(.+?)\]\]")

    def format(self, text: str) -> str:
        return self._TERM.sub(
            lambda m: f'<span dir="ltr" class="term">{m.group(1)}</span>', text)
