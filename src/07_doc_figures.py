"""
Meridian Health Network: 30-day readmission case study
Step 7: combined figures for the written case study

Run after 06_further_analysis.py.
Pairs related charts into single figures so the report carries fewer, denser exhibits.
The individual charts stay in outputs/figures for the GitHub repository.

Output: outputs/figures/combined/*.png
"""
from PIL import Image

from style import FIGURES

OUT = FIGURES / "combined"
OUT.mkdir(exist_ok=True)

PAIRS = {
    "A_cleaning_and_repeat_patients.png": (["02_cleaning_funnel.png", "03_repeat_patient_effect.png"], "vertical"),
    "B_length_of_stay.png": (["05_length_of_stay_distribution.png", "06_length_of_stay_by_outcome.png"], "vertical"),
    "C_age_and_diagnosis.png": (["09_readmission_by_age.png", "10_readmission_by_diagnosis.png"], "vertical"),
    "D_discrimination_and_calibration.png": (["14_roc_curve.png", "19_calibration.png"], "horizontal"),
    "E_deciles_and_capacity.png": (["15_lift_by_decile.png", "18_capacity_curve.png"], "vertical"),
    "F_prior_stays_and_discharge.png": (["07_readmission_by_prior_stays.png", "08_readmission_by_discharge.png"], "vertical"),
}
GAP = 60  # white space between panels, in pixels


def combine(files, direction):
    images = [Image.open(FIGURES / f).convert("RGB") for f in files]
    if direction == "vertical":
        width = max(i.width for i in images)
        height = sum(i.height for i in images) + GAP * (len(images) - 1)
        canvas = Image.new("RGB", (width, height), "white")
        y = 0
        for img in images:
            canvas.paste(img, (0, y))
            y += img.height + GAP
    else:
        width = sum(i.width for i in images) + GAP * (len(images) - 1)
        height = max(i.height for i in images)
        canvas = Image.new("RGB", (width, height), "white")
        x = 0
        for img in images:
            canvas.paste(img, (x, 0))
            x += img.width + GAP
    return canvas


for name, (files, direction) in PAIRS.items():
    combine(files, direction).save(OUT / name, optimize=True)
    print(f"Saved combined/{name}")
