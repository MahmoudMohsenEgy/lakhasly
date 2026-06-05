from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

class MatplotlibChartRenderer:
    def render(self, spec: dict, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 4))
        x, y = spec["x"], spec["y"]
        if spec.get("type", "bar") == "line":
            ax.plot(x, y, marker="o")
        else:
            ax.bar([str(v) for v in x], y)
        ax.set_title(spec.get("title", ""))
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return out_path
