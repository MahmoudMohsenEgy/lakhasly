import fitz
from explainer.state import LoadedSource, SourceImage
from explainer.interfaces import AssetStore

class PdfLoader:
    name = "pdf"

    def __init__(self, asset_store: AssetStore):
        self._assets = asset_store

    def can_handle(self, ref: str) -> bool:
        return ref.lower().endswith(".pdf")

    def load(self, ref: str) -> LoadedSource:
        doc = fitz.open(ref)
        text_parts, images = [], []
        for pno, page in enumerate(doc):
            text_parts.append(page.get_text("text"))
            for i, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                out = self._assets.allocate(".png")
                pix.save(out)
                images.append(SourceImage(id=f"p{pno}_{i}", path=out))
        return LoadedSource(text="\n".join(text_parts), images=images)
