"""
Meridian Health Network: 30-day readmission case study
Step 8: Power BI dashboard data

Run after 04_analysis.py and 05_model_evaluation.py.
Writes the eight CSV files the Power BI semantic model loads, so the dashboard and the
written case study come from the same pipeline run and use the same category groupings.

Output (outputs/powerbi/dashboard_data/, row-level, not published):
    patients.csv      one row per patient (69,987), risk scores for the 30% test set only
    Capacity.csv      capacity slicer values
    CapacityAxis.csv  capacity curve axis
    Scenario.csv      HYPOTHETICAL cost scenarios
    ModelMetrics.csv  fixed full-test metrics
    OddsRatios.csv    adjusted odds ratios with 95% CIs
    EffectSizes.csv   chi-square tests with Cramer's V and FDR p-values
    ROC.csv           ROC curve points

Also writes outputs/web/capacity-data.json and capacity-summary.csv: aggregate capacity results
for the portfolio web explorer. These hold no patient-level rows and can be published.
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from style import POWERBI, PROCESSED, TABLES

OUT = POWERBI / "dashboard_data"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(PROCESSED / "readmissions_clean.csv", low_memory=False)
scores = pd.read_csv(POWERBI / "test_scores.csv").set_index("row")["risk_score"]

# ---------------------------------------------------------------------------
# Patients: same groupings as the case study and the model
age_num = df["age_band"].str.split().str[0].astype(int)
race = df["race"].replace({"AfricanAmerican": "African American"})
admission = df["admission_type"].fillna("Other or unknown").replace(
    {"Newborn": "Other or unknown", "Trauma Center": "Other or unknown",
     "Not Mapped": "Other or unknown", "Not Available": "Other or unknown"})

patients = pd.DataFrame({
    "RowKey": np.arange(1, len(df) + 1),
    "AgeBand": df["age_band"],
    "AgeOrder": age_num + 5,
    "AgeGroup": pd.cut(age_num, [-1, 59, 79, 120], labels=["Under 60", "60-79", "80+"]).astype(str),
    "AgeGroupOrder": pd.cut(age_num, [-1, 59, 79, 120], labels=[1, 2, 3]).astype(int),
    "Gender": df["gender"],
    # Groups under 2% of patients are combined, as in section 8.3 of the case study
    "Race": race.where(race.isin(["Caucasian", "African American"]), "Other or unknown"),
    "Discharge": df["discharge_group"],
    "Diagnosis": df["primary_diagnosis_group"].replace({"Missing": "Other"}),
    "AdmissionType": admission,
    "LengthOfStay": df["time_in_hospital"],
    "LOSGroup": pd.cut(df["time_in_hospital"], [0, 2, 4, 7, 14],
                       labels=["1-2 days", "3-4 days", "5-7 days", "8-14 days"]).astype(str),
    "PriorInpatient": df["number_inpatient"],
    "PriorGroup": df["number_inpatient"].clip(upper=4).astype(str).replace("4", "4+"),
    "HbA1cTested": df["a1c_tested"],
    "HbA1cStatus": df["a1c_tested"].map({1: "Tested", 0: "Not tested"}),
    "Readmitted": df["readmitted_30"],
})
patients["IsTest"] = patients.index.isin(scores.index).astype(int)
patients["RiskScore"] = scores.reindex(patients.index)

test = patients["IsTest"] == 1
s = patients.loc[test, "RiskScore"]
patients.loc[test, "RiskDecile"] = pd.qcut(s.rank(method="first", ascending=False), 10,
                                           labels=range(1, 11)).astype(int)
patients.loc[test, "ReferenceFlag20"] = (s >= np.quantile(s, 0.80)).astype(int)
patients["RiskDecile"] = patients["RiskDecile"].astype("Int64")
patients["ReferenceFlag20"] = patients["ReferenceFlag20"].astype("Int64")
patients.to_csv(OUT / "patients.csv", index=False, float_format="%.12g")

# ---------------------------------------------------------------------------
# Small lookup and result tables
shares = pd.DataFrame({"Share": np.round(np.arange(0.05, 0.501, 0.05), 2)})
shares.to_csv(OUT / "Capacity.csv", index=False)
shares.to_csv(OUT / "CapacityAxis.csv", index=False)

pd.DataFrame([
    {"Scenario": "Conservative", "FollowUpCost": 150, "PreventionRate": 0.05, "AvoidedCost": 10000},
    {"Scenario": "Base", "FollowUpCost": 100, "PreventionRate": 0.10, "AvoidedCost": 12500},
    {"Scenario": "Optimistic", "FollowUpCost": 75, "PreventionRate": 0.20, "AvoidedCost": 15000},
]).to_csv(OUT / "Scenario.csv", index=False)

pd.read_csv(TABLES / "model_evaluation.csv").to_csv(OUT / "ModelMetrics.csv", index=False)
pd.read_csv(TABLES / "odds_ratios.csv").to_csv(OUT / "OddsRatios.csv", index=False)
pd.read_csv(TABLES / "chi_square_tests.csv").to_csv(OUT / "EffectSizes.csv", index=False)

# ROC curve, thinned to about 180 points for the chart
y_t = patients.loc[test, "Readmitted"]
fpr, tpr, _ = roc_curve(y_t, s)
keep = np.unique(np.round(np.linspace(0, len(fpr) - 1, 180)).astype(int))
pd.DataFrame({"FPR": fpr[keep], "TPR": tpr[keep]}).to_csv(OUT / "ROC.csv", index=False)

# ---------------------------------------------------------------------------
# Aggregate capacity results for the portfolio web explorer (no patient-level rows).
# One threshold is set on all test patients, as in the dashboard, then applied to each age group.
WEB = POWERBI.parent / "web"
WEB.mkdir(parents=True, exist_ok=True)
t = patients.loc[test, ["AgeGroup", "RiskScore", "Readmitted"]]
web, rows = {}, []
for group in ["All ages", "Under 60", "60-79", "80+"]:
    g = t if group == "All ages" else t[t["AgeGroup"] == group]
    web[group] = {}
    for pct in range(5, 55, 5):
        cut = np.percentile(t["RiskScore"], 100 - pct)  # same as DAX PERCENTILEX.INC
        flagged = g["RiskScore"] >= cut
        captured = int(g.loc[flagged, "Readmitted"].sum())
        actual = int(g["Readmitted"].sum())
        d = {"patients": len(g), "flags": int(flagged.sum()), "captured": captured,
             "missed": actual - captured, "actual": actual,
             "precision": round(captured / flagged.sum(), 6), "recall": round(captured / actual, 6),
             "threshold": round(float(cut), 6)}
        web[group][str(pct)] = d
        rows.append({"age_group": group, "requested_capacity_pct": pct, "test_patients": d["patients"],
                     "flagged": d["flags"], "captured_readmissions": captured,
                     "missed_readmissions": d["missed"], "precision": d["precision"],
                     "recall": d["recall"], "risk_threshold": d["threshold"]})
(WEB / "capacity-data.json").write_text(json.dumps(web, separators=(",", ":")))

# Aggregate counts for the web overview dashboard. Each table is grouped by the four filter
# fields plus one breakdown field, so the browser can filter and re-sum without any patient rows.
FILTERS = ["AgeGroup", "Gender", "Race", "Discharge"]
BREAKDOWNS = {"discharge": "Discharge", "prior": "PriorGroup", "age": "AgeBand",
              "los": "LOSGroup", "diagnosis": "Diagnosis", "stay": "LengthOfStay"}
levels = {f: sorted(patients[f].unique().tolist()) for f in FILTERS}
levels["AgeGroup"] = ["Under 60", "60-79", "80+"]
overview = {"filters": {f: levels[f] for f in FILTERS}, "tables": {}}
for key, col in BREAKDOWNS.items():
    keys = FILTERS + ([col] if col not in FILTERS else [])
    g = (patients.groupby(keys, observed=True)
         .agg(n=("Readmitted", "size"), r=("Readmitted", "sum"), h=("HbA1cTested", "sum"))
         .reset_index())
    cats = (sorted(g[col].unique().tolist()) if col != "AgeBand"
            else sorted(g[col].unique().tolist(), key=lambda b: int(b.split()[0])))
    cube = [[levels[f].index(r[f]) for f in FILTERS] + [cats.index(r[col]), int(r.n), int(r.r), int(r.h)]
            for _, r in g.iterrows()]
    overview["tables"][key] = {"categories": [str(c) for c in cats], "rows": cube}
(WEB / "overview-data.json").write_text(json.dumps(overview, separators=(",", ":")))
pd.DataFrame(rows).to_csv(WEB / "capacity-summary.csv", index=False)

# ---------------------------------------------------------------------------
# Check against the case study
flag = patients.loc[test, "ReferenceFlag20"] == 1
tp = int((flag & (y_t == 1)).sum())
print(f"Patients {len(patients):,}, test {int(test.sum()):,}, flagged {int(flag.sum()):,}, "
      f"true positives {tp:,}, recall {tp / y_t.sum():.2%}")
for col in ["Race", "Discharge", "Diagnosis", "AdmissionType"]:
    print(col, patients[col].value_counts().to_dict())
