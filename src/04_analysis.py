"""
Meridian Health Network: 30-day readmission case study
Step 4: statistical tests and readmission risk model

Run after 01_clean_data.py.
Input:  data/processed/readmissions_clean.csv
Output: outputs/tables/chi_square_tests.csv, numeric_tests.csv, model_metrics.csv,
        lift_by_decile.csv, odds_ratios.csv
        outputs/powerbi/readmissions_scored.csv  (test patients with risk scores, for Power BI)
        outputs/figures/13 to 17 *.png

Measures used: chi-square, Cramer's V, Mann-Whitney U, Welch t-test, Cohen's d, p-values,
logistic regression, confusion matrix, precision, recall, F1, AUC-ROC and lift.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score, roc_curve)
import statsmodels.api as sm
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from style import (CONTEXT, GRID, INK, INK_2, NHS_BLUE, NHS_ORANGE, POWERBI, PROCESSED, TABLES,
                   finish as _finish, title)


def finish(fig, name, note="69,987 patients, first stay only"):
    _finish(fig, name, note)


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


df = pd.read_csv(PROCESSED / "readmissions_clean.csv", low_memory=False)
y = df["readmitted_30"]
df["prior_inpatient"] = df["number_inpatient"].clip(upper=4).astype(str).replace("4", "4 or more")
df["a1c_status"] = df["a1c_tested"].map({1: "Tested", 0: "Not tested"})
df["los_band"] = pd.cut(df["time_in_hospital"], [0, 2, 4, 7, 14],
                        labels=["1 to 2 days", "3 to 4 days", "5 to 7 days", "8 to 14 days"]).astype(str)

# ---------------------------------------------------------------------------
# A. Chi-square tests with Cramer's V effect size
cat_tests = {
    "prior_inpatient": "Prior inpatient stays",
    "discharge_group": "Discharge destination",
    "los_band": "Length of first stay",
    "age_band": "Age band",
    "primary_diagnosis_group": "Primary diagnosis",
    "admission_source_group": "Admission source",
    "admission_type": "Admission type",
    "a1c_status": "HbA1c tested",
    "race": "Race",
    "gender": "Gender",
}
rows = []
for col, label in cat_tests.items():
    table = pd.crosstab(df[col], y)
    chi2, p, dof, _ = stats.chi2_contingency(table)
    v = np.sqrt(chi2 / (table.values.sum() * (min(table.shape) - 1)))
    rows.append({"factor": label, "chi2": chi2, "dof": dof, "p_value": p, "cramers_v": v})
chi = pd.DataFrame(rows)
# Exploratory tests: Benjamini-Hochberg false discovery rate adjustment across all 10 factors
chi["p_fdr"] = stats.false_discovery_control(chi["p_value"], method="bh")
chi = chi.sort_values("cramers_v", ascending=False)
chi.round(5).to_csv(TABLES / "chi_square_tests.csv", index=False)

# ---------------------------------------------------------------------------
# B. Numeric comparisons: Mann-Whitney U (skewed) and Welch t-test with Cohen's d
num_tests = {
    "time_in_hospital": "Length of stay (days)",
    "num_medications": "Medications",
    "number_diagnoses": "Diagnoses recorded",
    "num_lab_procedures": "Lab procedures",
    "number_inpatient": "Inpatient stays, prior year",
    "number_emergency": "Emergency visits, prior year",
}
rows = []
for col, label in num_tests.items():
    a, b = df.loc[y == 1, col], df.loc[y == 0, col]
    u, p_u = stats.mannwhitneyu(a, b, alternative="two-sided")
    t, p_t = stats.ttest_ind(a, b, equal_var=False)
    pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
    rows.append({"measure": label, "median_readmitted": a.median(), "median_not": b.median(),
                 "mean_readmitted": a.mean(), "mean_not": b.mean(),
                 "mann_whitney_p": p_u, "welch_t": t, "welch_p": p_t,
                 "cohens_d": (a.mean() - b.mean()) / pooled})
num = pd.DataFrame(rows)
num.round(4).to_csv(TABLES / "numeric_tests.csv", index=False)

# Chart 13: effect size of each factor
fig, ax = plt.subplots(figsize=(8, 4.8))
c = chi.iloc[::-1]
colours = [NHS_ORANGE if v >= 0.05 else NHS_BLUE if p < 0.05 else CONTEXT
           for v, p in zip(c["cramers_v"], c["p_fdr"])]
ax.barh(c["factor"], c["cramers_v"], color=colours, height=0.6)
lab = ax.get_yaxis_transform()
for i, (_, r) in enumerate(c.iterrows()):
    ax.text(1.02, i, f"V = {r['cramers_v']:.3f}", transform=lab, va="center", fontsize=10,
            color=INK, fontweight="bold")
    ax.text(1.25, i, f"FDR p {fmt_p(r['p_fdr'])}", transform=lab, va="center", fontsize=9.5, color=INK_2)
ax.set_xlabel("Effect size (Cramér's V). 0.1 = small, 0.3 = medium")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
ax.set_xlim(0, c["cramers_v"].max() * 1.15)
title(fig, "Prior stays and discharge destination have the largest effects",
      "Exploratory chi-square tests, FDR-adjusted. Orange: V of 0.05 or more. "
      "Grey: not significant")
finish(fig, "13_effect_sizes.png")

# ---------------------------------------------------------------------------
# C. Logistic regression risk model
numeric = ["number_inpatient", "number_emergency", "number_outpatient", "time_in_hospital",
           "num_medications", "number_diagnoses", "num_lab_procedures", "num_procedures",
           "age_mid", "med_changes", "a1c_tested"]
categorical = ["discharge_group", "admission_source_group", "admission_type",
               "primary_diagnosis_group", "insulin", "diabetesMed", "gender"]
df[categorical] = df[categorical].fillna("Not Available")
# Group rare or uninformative categories so every level has enough patients to estimate
df["admission_type"] = df["admission_type"].replace(
    {"Newborn": "Other or unknown", "Trauma Center": "Other or unknown",
     "Not Mapped": "Other or unknown", "Not Available": "Other or unknown"})
df["primary_diagnosis_group"] = df["primary_diagnosis_group"].replace({"Missing": "Other"})
X = df[numeric + categorical]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)

model = Pipeline([
    ("prep", ColumnTransformer([
        ("num", StandardScaler(), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), categorical),
    ])),
    ("lr", LogisticRegression(C=np.inf, max_iter=5000)),
])

# 5-fold stratified cross-validation on all patients (one stay each, so no patient overlap)
cv = cross_val_score(model, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=42), scoring="roc_auc")
model.fit(X_train, y_train)
score = model.predict_proba(X_test)[:, 1]
auc = roc_auc_score(y_test, score)

# Flag the top 20% highest-risk patients for follow-up
cut = np.quantile(score, 0.80)
flag = (score >= cut).astype(int)
tn, fp, fn, tp = confusion_matrix(y_test, flag).ravel()
prec, rec, f1 = precision_score(y_test, flag), recall_score(y_test, flag), f1_score(y_test, flag)
base = y_test.mean()
metrics = pd.DataFrame([
    {"metric": "Test patients", "value": len(y_test)},
    {"metric": "Base readmission rate", "value": base},
    {"metric": "AUC-ROC", "value": auc},
    {"metric": "Cross-validated AUC, mean", "value": cv.mean()},
    {"metric": "Cross-validated AUC, SD", "value": cv.std()},
    {"metric": "Patients flagged (top 20%)", "value": int(flag.sum())},
    {"metric": "True positives", "value": int(tp)},
    {"metric": "False positives", "value": int(fp)},
    {"metric": "False negatives", "value": int(fn)},
    {"metric": "True negatives", "value": int(tn)},
    {"metric": "Precision", "value": prec},
    {"metric": "Recall", "value": rec},
    {"metric": "F1 score", "value": f1},
    {"metric": "Lift in flagged group", "value": prec / base},
])
metrics.round(4).to_csv(TABLES / "model_metrics.csv", index=False)

# Lift by decile
dec = pd.DataFrame({"score": score, "y": y_test.values})
dec["decile"] = pd.qcut(dec["score"].rank(method="first", ascending=False), 10, labels=range(1, 11))
lift = dec.groupby("decile", observed=True)["y"].agg(["count", "sum", "mean"]).reset_index()
lift.columns = ["decile", "patients", "readmitted", "rate"]
lift["lift"] = lift["rate"] / base
lift["cumulative_capture"] = lift["readmitted"].cumsum() / lift["readmitted"].sum()
lift.round(4).to_csv(TABLES / "lift_by_decile.csv", index=False)

# Odds ratios with 95% confidence intervals (per standard deviation for numeric fields).
# statsmodels refits the same unpenalised model on the same design matrix to get standard errors.
names = model.named_steps["prep"].get_feature_names_out()
design = model.named_steps["prep"].transform(X_train)
design = design.toarray() if hasattr(design, "toarray") else design
logit = sm.Logit(y_train.values, sm.add_constant(design)).fit(disp=0, maxiter=200)
ci = np.asarray(logit.conf_int())[1:]
odds = pd.DataFrame({
    "feature": names, "coef": logit.params[1:], "odds_ratio": np.exp(logit.params[1:]),
    "ci_low": np.exp(ci[:, 0]), "ci_high": np.exp(ci[:, 1]), "p_value": logit.pvalues[1:],
})
odds["feature"] = (odds["feature"].str.replace("num__", "").str.replace("cat__", "")
                   .str.replace("_", " "))
odds.sort_values("odds_ratio", ascending=False).round(4).to_csv(TABLES / "odds_ratios.csv", index=False)

# Chart 14: ROC curve
fpr, tpr, _ = roc_curve(y_test, score)
fig, ax = plt.subplots(figsize=(6.5, 5.4))
ax.plot([0, 1], [0, 1], color=CONTEXT, linestyle="--", linewidth=1.5)
ax.plot(fpr, tpr, color=NHS_BLUE, linewidth=2)
ax.text(0.98, 0.3, "Random guess", color=INK_2, fontsize=9.5, ha="right", rotation=0)
ax.text(0.55, 0.62, f"Model AUC {auc:.2f}", color=NHS_BLUE, fontsize=11, fontweight="bold")
ax.set_xlabel("False positive rate (1 − specificity)")
ax.set_ylabel("True positive rate (recall)")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.grid(True, color=GRID)
ax.set_axisbelow(True)
title(fig, f"The model separates risk better than chance (AUC {auc:.2f})",
      "ROC curve for the logistic regression on the 30% hold-out test set")
finish(fig, "14_roc_curve.png", f"{len(y_test):,} test patients")

# Chart 15: readmission rate and lift by risk decile
fig, ax = plt.subplots(figsize=(8, 4.6))
cols = [NHS_ORANGE if d <= 2 else NHS_BLUE for d in lift["decile"].astype(int)]
ax.bar(lift["decile"].astype(int), lift["rate"] * 100, color=cols, width=0.7)
for d, r, l in zip(lift["decile"].astype(int), lift["rate"], lift["lift"]):
    ax.text(d, r * 100 - 0.3, f"{r * 100:.1f}%\n×{l:.1f}", ha="center", va="top", fontsize=9,
            color=INK if d <= 2 else "white", fontweight="bold")
ax.axhline(base * 100, color=INK_2, linestyle="--", linewidth=1)
ax.text(10.45, base * 100 - 0.3, f"Average {base * 100:.1f}%", fontsize=9, color=INK_2, ha="right", va="top")
ax.set_xticks(range(1, 11))
ax.set_xticklabels(["1\nhighest"] + [str(i) for i in range(2, 10)] + ["10\nlowest"])
ax.set_xlabel("Risk decile (10% of patients each)")
ax.set_ylabel("30-day readmission rate (%)")
ax.set_ylim(0, lift["rate"].max() * 100 * 1.25)
ax.yaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
top2 = lift.loc[lift["decile"].astype(int) <= 2, "readmitted"].sum() / lift["readmitted"].sum()
title(fig, f"The top 20% of risk scores hold {top2 * 100:.0f}% of readmissions",
      "Actual readmission rate in each risk decile, with lift against the average")
finish(fig, "15_lift_by_decile.png", f"{len(y_test):,} test patients")

# Chart 16: confusion matrix at the top-20% cut-off
fig, ax = plt.subplots(figsize=(6.8, 4.8))
cells = [[tn, fp], [fn, tp]]
labels = [["True negative", "False positive"], ["False negative", "True positive"]]
shade = [[GRID, CONTEXT], [CONTEXT, NHS_BLUE]]
for i in range(2):
    for j in range(2):
        ax.add_patch(plt.Rectangle((j, 1 - i), 1, 1, color=shade[i][j], ec="white", lw=3))
        txt = "white" if shade[i][j] == NHS_BLUE else INK
        ax.text(j + 0.5, 1.58 - i, f"{cells[i][j]:,}", ha="center", fontsize=18, color=txt, fontweight="bold")
        ax.text(j + 0.5, 1.32 - i, labels[i][j], ha="center", fontsize=10, color=txt)
ax.set_xlim(0, 2)
ax.set_ylim(0, 2)
ax.set_xticks([0.5, 1.5])
ax.set_xticklabels(["Not flagged", "Flagged for follow-up"])
ax.set_yticks([1.5, 0.5])
ax.set_yticklabels(["Not readmitted", "Readmitted"])
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
title(fig, f"Flagging 20% of patients catches {rec * 100:.0f}% of readmissions",
      f"Precision {prec * 100:.1f}%, recall {rec * 100:.1f}%, F1 {f1:.2f}. Rows: actual. Columns: predicted")
finish(fig, "16_confusion_matrix.png", f"{len(y_test):,} test patients")

# Chart 17: forest plot of the strongest factors, with 95% confidence intervals
o = odds[~odds["feature"].str.contains("unknown")].copy()
o["distance"] = np.abs(np.log(o["odds_ratio"]))
o = o.sort_values("distance", ascending=False).head(12).sort_values("odds_ratio")
nice = {
    "number inpatient": "Prior inpatient stays (per SD)",
    "number emergency": "Prior emergency visits (per SD)",
    "number outpatient": "Prior outpatient visits (per SD)",
    "time in hospital": "Length of stay (per SD)",
    "number diagnoses": "Diagnoses recorded (per SD)",
    "num medications": "Medications (per SD)",
    "age mid": "Age (per SD)",
}


def pretty(f):
    if f in nice:
        return nice[f]
    return f.replace("discharge group ", "Discharge: ").replace("admission source group ", "Source: ") \
            .replace("admission type ", "Admission type: ").replace("primary diagnosis group ", "Diagnosis: ") \
            .replace("insulin ", "Insulin: ").replace("diabetesMed ", "Diabetes drug: ").replace("gender ", "Gender: ")


fig, ax = plt.subplots(figsize=(8.5, 5.8))
yy = np.arange(len(o))
cols = [NHS_ORANGE if lo > 1 else NHS_BLUE if hi < 1 else CONTEXT
        for lo, hi in zip(o["ci_low"], o["ci_high"])]
ax.hlines(yy, o["ci_low"], o["ci_high"], color=cols, linewidth=2)
ax.scatter(o["odds_ratio"], yy, color=cols, s=55, zorder=3)
ax.axvline(1, color=INK, linewidth=1)
ax.set_xscale("log")
ticks = [0.5, 0.75, 1, 1.5, 2, 3, 4]
ax.set_xticks(ticks)
ax.set_xticklabels([str(t) for t in ticks])
ax.minorticks_off()
ax.set_yticks(yy)
ax.set_yticklabels([pretty(f) for f in o["feature"]])
lab = ax.get_yaxis_transform()
for i, (_, r) in enumerate(o.iterrows()):
    ax.text(1.02, i, f"{r['odds_ratio']:.2f}", transform=lab, va="center", fontsize=10,
            color=INK, fontweight="bold")
    ax.text(1.12, i, f"({r['ci_low']:.2f} to {r['ci_high']:.2f})", transform=lab, va="center",
            fontsize=9, color=INK_2)
ax.set_xlabel("Odds ratio, 95% CI, log scale. Compared with discharge home and circulatory diagnosis")
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
title(fig, "Discharge to other care and prior stays drive readmission risk",
      "Adjusted for all other factors. Orange raises risk, blue lowers it, grey is not significant")
finish(fig, "17_odds_ratios.png", f"Model trained on {len(X_train):,} patients")

# ---------------------------------------------------------------------------
# D. Power BI export: test patients with risk score, decile and flag
out = X_test.copy()
out["readmitted_30"] = y_test.values
out["risk_score"] = score.round(4)
out["risk_decile"] = dec["decile"].astype(int).values
out["flag_follow_up"] = flag
out = out.join(df.loc[X_test.index, ["age_band", "race", "los_band", "prior_inpatient"]])
out.to_csv(POWERBI / "readmissions_scored.csv", index=False)

# Full-precision test scores keyed by cleaned-file row, used by 08_powerbi_export.py
pd.DataFrame({"row": X_test.index, "risk_score": score}).to_csv(POWERBI / "test_scores.csv", index=False)

print(chi.round(4).to_string(index=False))
print(num.round(3).to_string(index=False))
print(metrics.round(4).to_string(index=False))
print(lift.round(3).to_string(index=False))
print(odds.sort_values("odds_ratio").round(3).to_string(index=False))
