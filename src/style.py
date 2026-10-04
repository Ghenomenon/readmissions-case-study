"""
Shared paths and chart style for the readmission case study.

Charts follow NHS identity colours: NHS Blue for focus, NHS Orange for the key
contrast, grey for context. Every chart carries an action title, a subtitle
with scope, direct labels and a source line.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Paths
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"
POWERBI = ROOT / "outputs" / "powerbi"
for folder in (PROCESSED, FIGURES, TABLES, POWERBI):
    folder.mkdir(parents=True, exist_ok=True)

# Colours
NHS_BLUE = "#005EB8"
NHS_ORANGE = "#ED8B00"
CONTEXT = "#AEB7BD"
INK = "#212B32"
INK_2 = "#425563"
GRID = "#E8EDEE"

SOURCE = "Source: UCI Diabetes 130-US Hospitals, 1999 to 2008."
AUTHOR = "Analysis: C. Nkwopara."

# Discharge codes for death or hospice: these patients cannot be readmitted
DEATH_HOSPICE_CODES = [11, 13, 14, 19, 20, 21]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def title(fig, main, sub):
    """Left-aligned action title and subtitle at the top of the figure."""
    fig.text(0.01, 0.985, main, fontsize=14, color=INK, fontweight="bold", va="top")
    fig.text(0.01, 0.985 - 0.32 / fig.get_figheight(), sub, fontsize=10.5, color=INK_2, va="top")


def finish(fig, name, note=None):
    """Add the source line, fit the layout and save to outputs/figures."""
    line = f"{SOURCE} {note}. {AUTHOR}" if note else f"{SOURCE} {AUTHOR}"
    fig.text(0.01, 0.01, line, fontsize=8.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1 - 0.75 / fig.get_figheight()))
    fig.savefig(FIGURES / name, bbox_inches="tight")
    plt.close(fig)
