from explainer.state import LoadedSource
from explainer.interfaces import SourceLoader

class LoaderRegistry:
    def __init__(self, loaders: list[SourceLoader]):
        self._loaders = loaders

    def load(self, ref: str, declared_type: str = "auto") -> LoadedSource:
        if declared_type != "auto":
            for ldr in self._loaders:
                if ldr.name == declared_type:
                    return ldr.load(ref)
            raise ValueError(f"No loader named '{declared_type}'")
        for ldr in self._loaders:
            if ldr.name != "text" and ldr.can_handle(ref):
                return ldr.load(ref)
        for ldr in self._loaders:
            if ldr.name == "text":
                return ldr.load(ref)
        raise ValueError(f"No loader could handle '{ref}'")
