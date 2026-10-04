"""
Meridian Health Network: 30-day readmission case study
Step 2: data quality and cleaning charts

Run after 01_clean_data.py.
Input:  data/raw/diabetic_data.csv, data/processed/cleaning_log.csv
Output: outputs/figures/01_missing_data.png
        outputs/figures/02_cleaning_funnel.png
        outputs/figures/03_repeat_patient_effect.png
"""
import matplotlib.pyplot as plt
import pandas as pd

from style import (CONTEXT, DEATH_HOSPICE_CODES, GRID, INK, NHS_BLUE, NHS_ORANGE,
                   PROCESSED, RAW, finish, title)


raw = pd.read_csv(RAW / "diabetic_data.csv", na_values="?", low_memory=False)
log = pd.read_csv(PROCESSED / "cleaning_log.csv")

# Chart 1: missing data by column, coloured by the cleaning action taken
missing = (raw.isna().mean() * 100).sort_values()
missing = missing[missing > 0]
dropped = {"weight", "payer_code", "medical_specialty", "max_glu_serum"}
recoded = {"A1Cresult"}
labels = {
    "weight": "Weight", "max_glu_serum": "Glucose serum test", "A1Cresult": "HbA1c result",
    "medical_specialty": "Medical specialty", "payer_code": "Payer code", "race": "Race",
    "diag_3": "Diagnosis 3", "diag_2": "Diagnosis 2", "diag_1": "Diagnosis 1",
}
colours = [NHS_BLUE if c in dropped else NHS_ORANGE if c in recoded else CONTEXT for c in missing.index]

fig, ax = plt.subplots(figsize=(8, 4.8))
bars = ax.barh([labels.get(c, c) for c in missing.index], missing.values, color=colours, height=0.6)
for bar, value, col in zip(bars, missing.values, missing.index):
    action = "dropped" if col in dropped else "recoded to 'Not tested'" if col in recoded else "kept"
    shown = "<0.1%" if value < 0.05 else f"{value:.1f}%"
    ax.text(value + 1, bar.get_y() + bar.get_height() / 2, f"{shown}  {action}",
            va="center", fontsize=9.5, color=INK)
ax.set_xlim(0, 125)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xlabel("Share of stays with no value (%)")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
title(fig, "Four fields were too empty to use",
      "Missing values by field in the raw extract, 101,766 stays")
finish(fig, "01_missing_data.png")

# Chart 2: rows remaining after each cleaning step, driven by cleaning_log.csv
step_labels = [
    "Raw extract", "Drop 4 sparse columns", "Remove invalid gender",
    "Remove deaths and hospice", "Keep first stay per patient", "Decode codes, add 12 fields",
]
rows = log["rows"].tolist()
removed = [0] + [rows[i - 1] - rows[i] for i in range(1, len(rows))]

fig, ax = plt.subplots(figsize=(8, 4.6))
y = list(range(len(rows)))[::-1]
bar_colours = [CONTEXT] * len(rows)
bar_colours[4] = NHS_ORANGE
bar_colours[-1] = NHS_BLUE
ax.barh(y, rows, color=bar_colours, height=0.6)
for yi, r, rem, i in zip(y, rows, removed, range(len(rows))):
    note = f"{r:,}"
    if rem:
        note += f"   (−{rem:,})"
    ax.text(r + 1500, yi, note, va="center", fontsize=9.5, color=INK)
ax.set_yticks(y)
ax.set_yticklabels(step_labels)
ax.set_xlim(0, 135000)
ax.set_xticks([0, 25000, 50000, 75000, 100000])
ax.set_xticklabels(["0", "25k", "50k", "75k", "100k"])
ax.set_xlabel("Rows remaining")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
title(fig, "Keeping one stay per patient removed 29,353 rows",
      "Rows after each cleaning step. Final dataset: 69,987 patients, one stay each")
finish(fig, "02_cleaning_funnel.png")

# Chart 3: why repeat stays were removed
alive = raw[~raw["discharge_disposition_id"].isin(DEATH_HOSPICE_CODES)].copy()
stays = alive["patient_nbr"].map(alive["patient_nbr"].value_counts())
alive["group"] = (stays > 1).map({False: "One stay", True: "Two or more stays"})
rate = alive.groupby("group")["readmitted"].apply(lambda s: (s == "<30").mean() * 100)
counts = alive.groupby("group").size()

fig, ax = plt.subplots(figsize=(8, 3.4))
groups = ["One stay", "Two or more stays"]
vals = [rate[g] for g in groups]
ax.barh(groups[::-1], vals[::-1], color=[NHS_ORANGE, CONTEXT], height=0.55)
for g, v in zip(groups[::-1], vals[::-1]):
    ax.text(v + 0.4, g, f"{v:.1f}%   ({counts[g]:,} stays)", va="center", fontsize=10, color=INK)
ax.set_xlim(0, 28)
ax.set_xlabel("30-day readmission rate (%)")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
title(fig, "Repeat patients readmit at over four times the rate",
      "Recurrent stays carry real signal. One index stay per patient was kept to avoid correlated data")
finish(fig, "03_repeat_patient_effect.png")

print("Saved charts 01 to 03")
