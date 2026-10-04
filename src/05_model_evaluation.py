"""
Meridian Health Network: 30-day readmission case study
Step 5: model evaluation, capacity scenarios, fairness and business case

Run after 04_analysis.py.
Input:  outputs/powerbi/readmissions_scored.csv  (hold-out test patients with risk scores)
Output: outputs/tables/model_evaluation.csv
        outputs/tables/capacity_scenarios.csv
        outputs/tables/fairness_by_group.csv
        outputs/tables/business_case_scenarios.csv
        outputs/figures/18_capacity_curve.png
        outputs/figures/19_calibration.png

The business case uses HYPOTHETICAL cost inputs, labelled as such. Meridian is fictional
and no real cost data exists for it. The inputs show how the decision would be modelled.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from style import (CONTEXT, GRID, INK, INK_2, NHS_BLUE, NHS_ORANGE, POWERBI, TABLES,
                   finish, title)

df = pd.read_csv(POWERBI / "readmissions_scored.csv")
y = df["readmitted_30"].to_numpy()
score = df["risk_score"].to_numpy()
N = len(df)
base = y.mean()
NOTE = f"{N:,} hold-out test patients"

# ---------------------------------------------------------------------------
# A. Discrimination and calibration metrics
rng = np.random.default_rng(42)
boot = []
for _ in range(1000):
    idx = rng.integers(0, N, N)
    if y[idx].min() != y[idx].max():
        boot.append(roc_auc_score(y[idx], score[idx]))
auc = roc_auc_score(y, score)
auc_lo, auc_hi = np.percentile(boot, [2.5, 97.5])
pr_auc = average_precision_score(y, score)
brier = brier_score_loss(y, score)
brier_null = brier_score_loss(y, np.full(N, base))

evaluation = pd.DataFrame([
    {"metric": "AUC-ROC", "value": auc},
    {"metric": "AUC-ROC 95% CI low (bootstrap, 1,000 resamples)", "value": auc_lo},
    {"metric": "AUC-ROC 95% CI high", "value": auc_hi},
    {"metric": "PR-AUC (average precision)", "value": pr_auc},
    {"metric": "PR-AUC of a random model (= readmission rate)", "value": base},
    {"metric": "Brier score", "value": brier},
    {"metric": "Brier score of a no-skill model", "value": brier_null},
    {"metric": "Brier skill score", "value": 1 - brier / brier_null},
    {"metric": "Mean predicted risk", "value": score.mean()},
    {"metric": "Observed readmission rate", "value": base},
])
evaluation.round(4).to_csv(TABLES / "model_evaluation.csv", index=False)

# Chart 19: calibration curve (10 equal-sized risk groups)
obs, pred = calibration_curve(y, score, n_bins=10, strategy="quantile")
fig, ax = plt.subplots(figsize=(6.8, 5.4))
lim = max(obs.max(), pred.max()) * 100 * 1.15
ax.plot([0, lim], [0, lim], color=CONTEXT, linestyle="--", linewidth=1.5)
ax.plot(pred * 100, obs * 100, color=NHS_BLUE, linewidth=2, marker="o", markersize=7)
ax.text(lim * 0.97, lim * 0.90, "Perfect calibration", color=INK_2, fontsize=9.5, ha="right")
ax.set_xlim(0, lim)
ax.set_ylim(0, lim)
ax.set_xlabel("Predicted readmission risk (%)")
ax.set_ylabel("Observed readmission rate (%)")
ax.grid(True, color=GRID)
ax.set_axisbelow(True)
title(fig, "Predicted risk tracks observed readmission reasonably closely",
      f"Calibration across 10 equal-sized risk groups. Brier score {brier:.3f}, no-skill model {brier_null:.3f}")
finish(fig, "19_calibration.png", NOTE)

# ---------------------------------------------------------------------------
# B. Capacity scenarios: what each follow-up capacity level would capture
order = np.argsort(-score)
y_sorted = y[order]
total_readmissions = y.sum()
rows = []
for share in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
    k = int(round(share * N))
    caught = y_sorted[:k].sum()
    rows.append({
        "capacity_share": share,
        "patients_followed_up_per_1000": share * 1000,
        "recall": caught / total_readmissions,
        "precision": caught / k,
        "lift": (caught / k) / base,
        "readmissions_in_group_per_1000": caught / N * 1000,
    })
capacity = pd.DataFrame(rows)

# Cumulative gains curve for chart 18
share_axis = np.arange(1, N + 1) / N
gain = np.cumsum(y_sorted) / total_readmissions

# ---------------------------------------------------------------------------
# C. Business case scenarios (HYPOTHETICAL inputs, per 1,000 diabetic discharges)
# Conservative = least favourable on every input.
scenarios = {
    "Conservative": {"cost_per_follow_up": 150, "prevention_rate": 0.05, "cost_per_readmission": 10000},
    "Base": {"cost_per_follow_up": 100, "prevention_rate": 0.10, "cost_per_readmission": 12500},
    "Optimistic": {"cost_per_follow_up": 75, "prevention_rate": 0.20, "cost_per_readmission": 15000},
}
row20 = capacity.loc[np.isclose(capacity["capacity_share"], 0.20)].iloc[0]
flagged = row20["patients_followed_up_per_1000"]
readmits_in_group = row20["readmissions_in_group_per_1000"]
case_rows = []
for name, s in scenarios.items():
    prevented = readmits_in_group * s["prevention_rate"]
    cost = flagged * s["cost_per_follow_up"]
    saving = prevented * s["cost_per_readmission"]
    case_rows.append({
        "scenario": name, **s,
        "patients_followed_up": flagged,
        "readmissions_in_flagged_group": readmits_in_group,
        "readmissions_prevented": prevented,
        "programme_cost": cost,
        "gross_saving": saving,
        "net_benefit": saving - cost,
        "cost_per_prevented_readmission": cost / prevented,
        "break_even_prevention_rate": cost / (readmits_in_group * s["cost_per_readmission"]),
    })
business = pd.DataFrame(case_rows)
business.round(3).to_csv(TABLES / "business_case_scenarios.csv", index=False)

# Base-case net benefit at each capacity level
b = scenarios["Base"]
capacity["base_net_benefit_per_1000"] = (
    capacity["readmissions_in_group_per_1000"] * b["prevention_rate"] * b["cost_per_readmission"]
    - capacity["patients_followed_up_per_1000"] * b["cost_per_follow_up"])
capacity.round(4).to_csv(TABLES / "capacity_scenarios.csv", index=False)

# Chart 18: cumulative gains with capacity scenarios marked
fig, ax = plt.subplots(figsize=(8, 5.2))
ax.plot([0, 100], [0, 100], color=CONTEXT, linestyle="--", linewidth=1.5)
ax.plot(share_axis * 100, gain * 100, color=NHS_BLUE, linewidth=2)
ax.text(62, 54, "Random selection", color=INK_2, fontsize=9.5, rotation=0)
for share, colour in [(0.10, NHS_BLUE), (0.20, NHS_ORANGE), (0.30, NHS_BLUE)]:
    r = capacity.loc[np.isclose(capacity["capacity_share"], share)].iloc[0]
    x, yv = share * 100, r["recall"] * 100
    ax.scatter([x], [yv], color=colour, s=70, zorder=3)
    ax.plot([x, x], [0, yv], color=colour, linewidth=1, linestyle=":")
    ax.text(x + 1.5, yv - 10, f"{share:.0%} capacity\ncatches {yv:.0f}%", fontsize=9.5, color=INK,
            fontweight="bold" if share == 0.20 else "normal")
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.set_xlabel("Share of patients followed up, highest risk first (%)")
ax.set_ylabel("Share of all 30-day readmissions captured (%)")
ax.grid(True, color=GRID)
ax.set_axisbelow(True)
title(fig, "Follow-up capacity sets how many readmissions the programme can reach",
      "Cumulative gains from ranking patients by risk score. The threshold is a planning choice")
finish(fig, "18_capacity_curve.png", NOTE)

# ---------------------------------------------------------------------------
# D. Subgroup performance at the 20% scenario threshold
cut = np.quantile(score, 0.80)
df["flag"] = (score >= cut).astype(int)
df["age_group"] = pd.cut(df["age_band"].str.split().str[0].astype(int), [-1, 59, 79, 120],
                         labels=["Under 60", "60 to 79", "80 and over"])
df["race_group"] = df["race"].where(df["race"].isin(["Caucasian", "AfricanAmerican"]), "Other or unknown")
df["race_group"] = df["race_group"].replace({"AfricanAmerican": "African American"})


def group_metrics(g):
    tp = ((g["flag"] == 1) & (g["readmitted_30"] == 1)).sum()
    fp = ((g["flag"] == 1) & (g["readmitted_30"] == 0)).sum()
    fn = ((g["flag"] == 0) & (g["readmitted_30"] == 1)).sum()
    tn = ((g["flag"] == 0) & (g["readmitted_30"] == 0)).sum()
    return pd.Series({
        "patients": len(g),
        "readmission_rate": g["readmitted_30"].mean(),
        "flagged_share": g["flag"].mean(),
        "recall": tp / (tp + fn) if tp + fn else np.nan,
        "precision": tp / (tp + fp) if tp + fp else np.nan,
        "false_positive_rate": fp / (fp + tn) if fp + tn else np.nan,
        "auc": roc_auc_score(g["readmitted_30"], g["risk_score"]),
    })


fair = []
for col, label in [("gender", "Sex"), ("race_group", "Race"), ("age_group", "Age")]:
    t = df.groupby(col, observed=True)[["flag", "readmitted_30", "risk_score"]].apply(group_metrics).reset_index()
    t = t.rename(columns={col: "group"})
    t.insert(0, "dimension", label)
    fair.append(t)
fairness = pd.concat(fair, ignore_index=True)
fairness.round(4).to_csv(TABLES / "fairness_by_group.csv", index=False)

print(evaluation.round(4).to_string(index=False))
print(capacity.round(3).to_string(index=False))
print(business.round(2).to_string(index=False))
print(fairness.round(3).to_string(index=False))
