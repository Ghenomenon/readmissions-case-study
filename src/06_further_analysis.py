"""
Meridian Health Network: 30-day readmission case study
Step 6: HbA1c testing variation, correlation of drivers, fairness root cause

Run after 05_model_evaluation.py.
Input:  data/processed/readmissions_clean.csv, outputs/powerbi/readmissions_scored.csv
Output: outputs/tables/hba1c_testing_by_group.csv
        outputs/tables/spearman_correlation.csv
        outputs/tables/fairness_inputs_by_race.csv
        outputs/tables/fairness_calibration_by_age_race.csv
        outputs/figures/20_hba1c_funnel.png
        outputs/figures/21_fairness_calibration.png
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from style import (CONTEXT, GRID, INK, INK_2, NHS_BLUE, NHS_ORANGE, POWERBI, PROCESSED, TABLES,
                   finish, title)


def wilson(k, n, z=1.96):
    p = k / n
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return p, centre - half, centre + half


df = pd.read_csv(PROCESSED / "readmissions_clean.csv", low_memory=False)

# ---------------------------------------------------------------------------
# A. HbA1c testing rate by subgroup, with z-scores against the overall rate
p0 = df["a1c_tested"].mean()
dims = {
    "age_band": "Age", "admission_type": "Admission type", "admission_source_group": "Admission source",
    "primary_diagnosis_group": "Primary diagnosis", "race": "Race", "gender": "Sex",
    "discharge_group": "Discharge",
}
rows = []
for col, label in dims.items():
    g = df.groupby(col)["a1c_tested"].agg(["sum", "count"])
    for name, r in g.iterrows():
        n = r["count"]
        p = r["sum"] / n
        rows.append({"dimension": label, "group": name, "patients": int(n), "testing_rate": p,
                     "z_score": (p - p0) / np.sqrt(p0 * (1 - p0) / n)})
a1c = pd.DataFrame(rows)
a1c = a1c[(a1c["patients"] >= 100) & ~a1c["group"].isin(["Not Available", "Not Mapped", "Other or unknown"])]
a1c = a1c.sort_values("z_score")
a1c.round(4).to_csv(TABLES / "hba1c_testing_by_group.csv", index=False)

tested = df[df["a1c_tested"] == 1]["A1Cresult"].value_counts(normalize=True)

# Chart 20: funnel plot (NHS standard for comparing rates across groups of different sizes)
fig, ax = plt.subplots(figsize=(9, 5.6))
n_axis = np.linspace(100, a1c["patients"].max() * 1.05, 400)
se = np.sqrt(p0 * (1 - p0) / n_axis)
for z, style_ in [(1.96, ":"), (3.09, "--")]:
    ax.plot(n_axis, (p0 + z * se) * 100, color=INK_2, linestyle=style_, linewidth=1)
    ax.plot(n_axis, (p0 - z * se) * 100, color=INK_2, linestyle=style_, linewidth=1)
ax.axhline(p0 * 100, color=INK, linewidth=1)
colours = [NHS_ORANGE if z > 3.09 else NHS_BLUE if z < -3.09 else CONTEXT for z in a1c["z_score"]]
ax.scatter(a1c["patients"], a1c["testing_rate"] * 100, c=colours, s=45, zorder=3,
           edgecolors="white", linewidths=0.8)
labels = {
    ("Primary diagnosis", "Diabetes"): (8, -3, "left"),
    ("Age", "40 to 50"): (8, 3, "left"),
    ("Admission source", "Emergency room"): (0, 9, "center"),
    ("Admission type", "Elective"): (8, -12, "left"),
    ("Primary diagnosis", "Musculoskeletal"): (-8, -12, "right"),
    ("Age", "80 to 90"): (-8, -10, "right"),
}
for _, r in a1c.iterrows():
    key = (r["dimension"], r["group"])
    if key in labels:
        dx, dy, ha = labels[key]
        ax.annotate(f"{r['dimension']}: {r['group']} ({r['testing_rate'] * 100:.0f}%)",
                    (r["patients"], r["testing_rate"] * 100), xytext=(dx, dy),
                    textcoords="offset points", fontsize=8.5, color=INK, ha=ha)
ax.text(105, p0 * 100 + 0.5, f"All patients {p0 * 100:.1f}%", ha="left", va="bottom", fontsize=9, color=INK)
ax.set_xscale("log")
ax.set_xticks([200, 500, 1000, 2000, 5000, 10000, 20000, 50000])
ax.set_xticklabels(["200", "500", "1k", "2k", "5k", "10k", "20k", "50k"])
ax.minorticks_off()
ax.set_ylim(0, 40)
ax.set_xlabel("Patients in group (log scale)")
ax.set_ylabel("HbA1c testing rate (%)")
ax.grid(True, color=GRID)
ax.set_axisbelow(True)
title(fig, "Elective and older patients are tested least, diabetes admissions most",
      "Funnel plot of HbA1c testing by subgroup. Lines: 95% and 99.8% limits. "
      "Orange above, blue below 99.8%")
finish(fig, "20_hba1c_funnel.png", "69,987 patients, first stay only. Groups under 100 hidden")

# ---------------------------------------------------------------------------
# B. Spearman correlation of numeric drivers, and with 30-day readmission
cols = {
    "time_in_hospital": "Length of stay", "num_lab_procedures": "Lab procedures",
    "num_procedures": "Other procedures", "num_medications": "Medications",
    "number_diagnoses": "Diagnoses", "number_inpatient": "Prior inpatient stays",
    "number_emergency": "Prior emergency visits", "number_outpatient": "Prior outpatient visits",
    "age_mid": "Age", "readmitted_30": "30-day readmission",
}
corr = df[list(cols)].corr(method="spearman").rename(index=cols, columns=cols)
corr.round(3).to_csv(TABLES / "spearman_correlation.csv")

# ---------------------------------------------------------------------------
# C. Fairness root cause: model inputs, calibration and recall by race (hold-out test set)
s = pd.read_csv(POWERBI / "readmissions_scored.csv")
s["race_group"] = s["race"].replace({"AfricanAmerican": "African American"})
s["race_group"] = s["race_group"].where(s["race_group"].isin(["African American", "Caucasian"]), "Other or unknown")
s["flag"] = (s["risk_score"] >= np.quantile(s["risk_score"], 0.80)).astype(int)
s["age_group"] = pd.cut(s["age_mid"], [0, 60, 80, 120], right=False,
                        labels=["Under 60", "60 to 79", "80 and over"])

inputs = s.groupby("race_group").agg(
    patients=("flag", "size"),
    observed_readmission=("readmitted_30", "mean"),
    mean_predicted_risk=("risk_score", "mean"),
    flagged_share=("flag", "mean"),
    mean_age=("age_mid", "mean"),
    under_60_share=("age_group", lambda x: (x == "Under 60").mean()),
    any_prior_inpatient=("number_inpatient", lambda x: (x > 0).mean()),
    discharged_to_nursing_or_rehab=("discharge_group",
                                    lambda x: x.isin(["Nursing facility", "Other inpatient or rehab"]).mean()),
)
inputs.round(4).to_csv(TABLES / "fairness_inputs_by_race.csv")

cal_rows = []
for (age, race), g in s[s["race_group"] != "Other or unknown"].groupby(["age_group", "race_group"], observed=True):
    k, n = g["readmitted_30"].sum(), len(g)
    p, lo, hi = wilson(k, n)
    pos = g[g["readmitted_30"] == 1]
    cal_rows.append({"age_group": age, "race_group": race, "patients": n, "readmitted": int(k),
                     "observed": p, "observed_ci_low": lo, "observed_ci_high": hi,
                     "mean_predicted": g["risk_score"].mean(), "flagged_share": g["flag"].mean(),
                     "recall": pos["flag"].mean()})
cal = pd.DataFrame(cal_rows)
cal.round(4).to_csv(TABLES / "fairness_calibration_by_age_race.csv", index=False)

# Chart 21: predicted against observed readmission by race within age group
fig, ax = plt.subplots(figsize=(8.5, 5.2))
order = [(a, r) for a in ["Under 60", "60 to 79", "80 and over"] for r in ["African American", "Caucasian"]]
cal_i = cal.set_index(["age_group", "race_group"])
ys = []
for i, key in enumerate(order[::-1]):
    r = cal_i.loc[key]
    y = i + (0.4 if i >= 2 else 0) + (0.4 if i >= 4 else 0)
    ys.append(y)
    ax.hlines(y, r["observed_ci_low"] * 100, r["observed_ci_high"] * 100, color=NHS_ORANGE, linewidth=2)
    ax.scatter(r["observed"] * 100, y, color=NHS_ORANGE, s=60, zorder=3,
               label="Observed (95% CI)" if i == 0 else None)
    ax.scatter(r["mean_predicted"] * 100, y, color=NHS_BLUE, marker="D", s=50, zorder=4,
               label="Predicted" if i == 0 else None)
    ax.text(16.2, y, f"recall {r['recall'] * 100:.0f}%   n={int(r['patients']):,}", va="center",
            fontsize=9, color=INK_2)
ax.set_yticks(ys)
ax.set_yticklabels([f"{a}: {r}" for a, r in order[::-1]])
ax.set_xlim(4, 16)
ax.set_xlabel("30-day readmission rate (%)")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
ax.legend(loc="upper right", frameon=False, fontsize=9)
title(fig, "The model under-predicts risk for African American patients aged 60 to 79",
      "Mean predicted risk against observed readmission, by race within age group, at the 20% scenario")
finish(fig, "21_fairness_calibration.png", f"{len(s):,} hold-out test patients")

print(a1c.round(3).to_string(index=False))
print(f"\nOf tested patients: {tested.round(3).to_dict()}")
print(corr.round(2).to_string())
print(inputs.round(3).to_string())
print(cal.round(3).to_string(index=False))
