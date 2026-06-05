import re

class BasicNormalizer:
    _FILLER = re.compile(r"^\s*\[(music|applause|laughter|inaudible)\]\s*$", re.IGNORECASE)

    def normalize(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            if self._FILLER.match(line):
                continue
            lines.append(re.sub(r"[ \t]+", " ", line).strip())
        out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        return out.strip()
