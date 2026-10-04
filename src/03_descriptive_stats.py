"""
Meridian Health Network: 30-day readmission case study
Step 3: descriptive statistics and charts

Run after 01_clean_data.py.
Input:  data/processed/readmissions_clean.csv
Output: outputs/tables/descriptive_summary.csv   (mean, median, SD, IQR, percentiles, skew)
        outputs/tables/readmission_by_group.csv  (rates with 95% confidence intervals)
        outputs/figures/04 to 12 *.png

Measures used: mean, median, standard deviation, interquartile range, percentiles,
skewness, percentage share, frequency count and 95% confidence intervals.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from style import (CONTEXT, GRID, INK, INK_2, NHS_BLUE, NHS_ORANGE, PROCESSED, TABLES,
                   finish as _finish, title)

NOTE = "69,987 patients, first stay only"


def finish(fig, name):
    _finish(fig, name, NOTE)


def wilson(k, n, z=1.96):
    """95% Wilson confidence interval for a proportion."""
    p = k / n
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return p, centre - half, centre + half


df = pd.read_csv(PROCESSED / "readmissions_clean.csv", low_memory=False)
N = len(df)
k = df["readmitted_30"].sum()
overall, lo, hi = wilson(k, N)

# ---------------------------------------------------------------------------
# Table 1: numeric summary
numeric = {
    "time_in_hospital": "Length of stay (days)",
    "num_lab_procedures": "Lab procedures",
    "num_procedures": "Other procedures",
    "num_medications": "Medications",
    "number_diagnoses": "Diagnoses recorded",
    "number_inpatient": "Inpatient stays, prior year",
    "number_emergency": "Emergency visits, prior year",
    "number_outpatient": "Outpatient visits, prior year",
    "age_mid": "Age (band midpoint)",
}
rows = []
for col, label in numeric.items():
    s = df[col]
    q1, q3 = s.quantile([0.25, 0.75])
    rows.append({
        "measure": label, "mean": s.mean(), "median": s.median(), "sd": s.std(),
        "q1": q1, "q3": q3, "iqr": q3 - q1,
        "p10": s.quantile(0.10), "p90": s.quantile(0.90),
        "min": s.min(), "max": s.max(), "skew": s.skew(),
    })
summary = pd.DataFrame(rows).round(2)
summary.to_csv(TABLES / "descriptive_summary.csv", index=False)

# ---------------------------------------------------------------------------
# Table 2: readmission rate by group, with 95% CI
def rate_table(col, order=None):
    g = df.groupby(col)["readmitted_30"].agg(["sum", "count"])
    out = []
    for name, r in g.iterrows():
        p, l, h = wilson(r["sum"], r["count"])
        out.append({"group_by": col, "group": name, "patients": int(r["count"]),
                    "readmitted": int(r["sum"]), "rate": p, "ci_low": l, "ci_high": h})
    t = pd.DataFrame(out)
    if order:
        t = t.set_index("group").loc[order].reset_index()
    return t


df["prior_inpatient"] = df["number_inpatient"].clip(upper=4).map(
    {0: "0", 1: "1", 2: "2", 3: "3", 4: "4 or more"})
df["a1c_status"] = df["a1c_tested"].map({1: "Tested", 0: "Not tested"})
df["los_band"] = pd.cut(df["time_in_hospital"], [0, 2, 4, 7, 14],
                        labels=["1 to 2 days", "3 to 4 days", "5 to 7 days", "8 to 14 days"])

age_order = sorted(df["age_band"].unique(), key=lambda a: int(a.split()[0]))
tables = {
    "age_band": rate_table("age_band", age_order),
    "discharge_group": rate_table("discharge_group"),
    "prior_inpatient": rate_table("prior_inpatient", ["0", "1", "2", "3", "4 or more"]),
    "primary_diagnosis_group": rate_table("primary_diagnosis_group"),
    "admission_source_group": rate_table("admission_source_group"),
    "a1c_status": rate_table("a1c_status"),
    "los_band": rate_table("los_band", ["1 to 2 days", "3 to 4 days", "5 to 7 days", "8 to 14 days"]),
}
pd.concat(tables.values()).round(4).to_csv(TABLES / "readmission_by_group.csv", index=False)


def rate_chart(t, path, main, sub, sort=True, min_n=100, ylabel=None):
    t = t[t["patients"] >= min_n].copy()
    if sort:
        t = t.sort_values("rate")
    else:
        t = t.iloc[::-1]
    top = t["rate"].idxmax()
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(t) + 1.9))
    colours = [NHS_ORANGE if i == top else NHS_BLUE for i in t.index]
    y = np.arange(len(t))
    ax.barh(y, t["rate"] * 100, color=colours, height=0.6)
    ax.errorbar(t["rate"] * 100, y,
                xerr=[(t["rate"] - t["ci_low"]) * 100, (t["ci_high"] - t["rate"]) * 100],
                fmt="none", ecolor=INK, elinewidth=1, capsize=3)
    lab = ax.get_yaxis_transform()
    for yi, (_, r) in zip(y, t.iterrows()):
        ax.text(1.02, yi, f"{r['rate'] * 100:.1f}%", transform=lab,
                va="center", fontsize=10, color=INK, fontweight="bold")
        ax.text(1.16, yi, f"n={r['patients']:,}", transform=lab,
                va="center", fontsize=9.5, color=INK_2)
    ax.axvline(overall * 100, color=INK_2, linestyle="--", linewidth=1)
    ax.text(overall * 100, len(t) - 0.35, f" All patients {overall * 100:.1f}%",
            fontsize=9, color=INK_2, va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels(t["group"].astype(str))
    ax.set_xlim(0, max(t["ci_high"].max(), overall) * 100 * 1.08)
    ax.set_ylim(-0.6, len(t) - 0.1)
    ax.set_xlabel(ylabel or "30-day readmission rate (%), with 95% confidence interval")
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    title(fig, main, sub)
    finish(fig, path)


# ---------------------------------------------------------------------------
# Chart 4: headline KPI panel
a1c_rate = df["a1c_tested"].mean()
los = df["time_in_hospital"]
kpis = [
    (f"{N:,}", "Patients analysed", "one stay each"),
    (f"{overall * 100:.1f}%", "30-day readmission", f"95% CI {lo * 100:.1f}% to {hi * 100:.1f}%"),
    (f"{los.median():.0f} days", "Median length of stay", f"mean {los.mean():.1f}, IQR {los.quantile(.25):.0f} to {los.quantile(.75):.0f}"),
    (f"{los.quantile(.9):.0f} days", "90th percentile stay", "1 in 10 stay this long or longer"),
    (f"{a1c_rate * 100:.1f}%", "HbA1c tested", "during the stay"),
    (f"{(df['number_inpatient'] > 0).mean() * 100:.0f}%", "Had a prior inpatient stay", "in the year before"),
]
fig, axes = plt.subplots(2, 3, figsize=(10, 4.2))
for ax, (big, label, note) in zip(axes.flat, kpis):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                               edgecolor=GRID, linewidth=1.5))
    colour = NHS_ORANGE if label.startswith("HbA1c") else NHS_BLUE
    ax.text(0.07, 0.62, big, fontsize=24, color=colour, fontweight="bold", transform=ax.transAxes)
    ax.text(0.07, 0.36, label, fontsize=11, color=INK, transform=ax.transAxes)
    ax.text(0.07, 0.16, note, fontsize=9, color=INK_2, transform=ax.transAxes)
title(fig, "About 1 in 11 diabetic patients returns within 30 days",
      "Headline measures for Meridian Health Network, diabetic inpatients")
finish(fig, "04_kpi_summary.png")

# ---------------------------------------------------------------------------
# Chart 5: length of stay distribution with mean, median and 90th percentile
fig, ax = plt.subplots(figsize=(8, 4.4))
counts = los.value_counts().sort_index()
ax.bar(counts.index, counts.values, color=NHS_BLUE, width=0.8)
marks = [(los.median(), "Median", "right"), (los.mean(), "Mean", "left"), (los.quantile(.9), "90th percentile", "left")]
ax.set_ylim(0, counts.max() * 1.3)
for x, lab, side in marks:
    ax.axvline(x, color=INK, linestyle="--", linewidth=1, ymax=0.97)
    ax.text(x + (0.15 if side == "left" else -0.15), counts.max() * 1.22, f"{lab}\n{x:.1f} days",
            fontsize=9, color=INK, ha=side, va="top")
ax.set_xticks(range(1, 15))
ax.set_xlabel("Length of stay (days)")
ax.set_ylabel("Patients")
ax.yaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
title(fig, f"Most stays are short, with a long tail (skew {los.skew():.2f})",
      f"Length of stay for {N:,} patients. Mean sits above the median because long stays pull it up")
finish(fig, "05_length_of_stay_distribution.png")

# ---------------------------------------------------------------------------
# Chart 6: length of stay by readmission status (box plot: median and IQR)
groups = [df.loc[df["readmitted_30"] == 0, "time_in_hospital"],
          df.loc[df["readmitted_30"] == 1, "time_in_hospital"]]
fig, ax = plt.subplots(figsize=(8, 3.6))
bp = ax.boxplot(groups, orientation="horizontal", widths=0.5, patch_artist=True, showfliers=False,
                medianprops={"color": INK, "linewidth": 2}, whiskerprops={"color": INK_2},
                capprops={"color": INK_2})
for patch, colour in zip(bp["boxes"], [CONTEXT, NHS_ORANGE]):
    patch.set_facecolor(colour)
    patch.set_edgecolor(colour)
for i, g in enumerate(groups, start=1):
    ax.text(15.2, i, f"median {g.median():.0f}, mean {g.mean():.1f}, IQR {g.quantile(.25):.0f} to {g.quantile(.75):.0f}",
            va="center", fontsize=9.5, color=INK)
ax.set_yticks([1, 2])
ax.set_yticklabels(["Not readmitted", "Readmitted within 30 days"])
ax.set_xlim(0, 26)
ax.set_xticks(range(0, 15, 2))
ax.set_xlabel("Length of stay (days)")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
title(fig, "Readmitted patients had longer first stays: median 4 days against 3",
      "First-stay length by outcome. Box = middle 50%, line = median, whiskers = range within 1.5 × IQR")
finish(fig, "06_length_of_stay_by_outcome.png")

# ---------------------------------------------------------------------------
# Charts 7 to 11: readmission rate by group
rate_chart(tables["prior_inpatient"], "07_readmission_by_prior_stays.png",
           "Readmission risk rises with every prior hospital stay",
           "30-day readmission rate by inpatient stays in the year before admission", sort=False)
rate_chart(tables["discharge_group"], "08_readmission_by_discharge.png",
           "Patients sent to rehab or other inpatient care readmit most",
           "30-day readmission rate by discharge destination. Groups under 100 patients hidden")
rate_chart(tables["age_band"], "09_readmission_by_age.png",
           "Readmission climbs gently with age after 50",
           "30-day readmission rate by age band. Bands under 100 patients hidden", sort=False)
rate_chart(tables["primary_diagnosis_group"], "10_readmission_by_diagnosis.png",
           "Injury and circulatory admissions readmit most often",
           "30-day readmission rate by primary diagnosis group (ICD-9)")
rate_chart(tables["los_band"], "11_readmission_by_length_of_stay.png",
           "Longer first stays carry higher readmission risk",
           "30-day readmission rate by length of the first stay", sort=False)

# ---------------------------------------------------------------------------
# Chart 12: HbA1c testing share and readmission
a1c_share = df["a1c_status"].value_counts(normalize=True)
fig, ax = plt.subplots(figsize=(8, 3.0))
left = 0
for status, colour in [("Tested", NHS_BLUE), ("Not tested", CONTEXT)]:
    w = a1c_share[status] * 100
    ax.barh([0], [w], left=left, color=colour, height=0.5, edgecolor="white", linewidth=2)
    r = tables["a1c_status"].set_index("group").loc[status]
    x, ha = (0.3, "left") if status == "Tested" else (99.7, "right")
    ax.text(x, 0.32, f"{status}: {w:.1f}% of patients",
            va="bottom", ha=ha, fontsize=10, color=INK, fontweight="bold")
    ax.text(x, -0.32, f"30-day readmission {r['rate'] * 100:.1f}%",
            va="top", ha=ha, fontsize=9.5, color=INK_2)
    left += w
ax.set_xlim(0, 100)
ax.set_ylim(-0.75, 0.75)
ax.set_yticks([])
ax.set_xlabel("Share of patients (%)")
ax.spines["left"].set_visible(False)
title(fig, "Fewer than 1 in 5 diabetic patients had an HbA1c test",
      "Share of patients with an HbA1c test during their stay, and their 30-day readmission rate")
finish(fig, "12_hba1c_testing.png")

print(summary.to_string(index=False))
print(f"\nOverall 30-day readmission: {overall:.4f} (95% CI {lo:.4f} to {hi:.4f})")
print("Saved tables and charts 04 to 12")
