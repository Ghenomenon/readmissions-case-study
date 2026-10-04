"""
Meridian Health Network: 30-day readmission case study
Step 1: data cleaning

Input:  data/raw/diabetic_data.csv, data/raw/IDS_mapping.csv
        (UCI Diabetes 130-US Hospitals, 1999 to 2008)
Output: data/processed/readmissions_clean.csv, data/processed/cleaning_log.csv
"""
import pandas as pd

from style import DEATH_HOSPICE_CODES, PROCESSED, RAW

log = []


def record(step, df, note=""):
    log.append({"step": step, "rows": len(df), "patients": df["patient_nbr"].nunique(), "note": note})
    print(f"{step:<45} rows={len(df):>7,} patients={df['patient_nbr'].nunique():>7,}  {note}")


# 1. Load, treating "?" as missing
df = pd.read_csv(RAW / "diabetic_data.csv", na_values="?", low_memory=False)
record("0. Raw data", df)

# 2. Drop columns that are mostly empty or carry no analytic value
missing = (df.isna().mean() * 100).round(1)
drop_cols = ["weight", "payer_code", "medical_specialty", "max_glu_serum"]
drop_cols = [c for c in drop_cols if c in df.columns]
note = ", ".join(f"{c} ({missing[c]}% missing)" for c in drop_cols)
# A1Cresult: missing means "not tested", so recode rather than drop
df["A1Cresult"] = df["A1Cresult"].fillna("Not tested")
df = df.drop(columns=drop_cols)
record("1. Drop sparse columns", df, note)

# 3. Remove invalid gender
df = df[df["gender"] != "Unknown/Invalid"]
record("2. Remove invalid gender", df)

# 4. Remove patients who died or went to hospice (cannot be readmitted)
df = df[~df["discharge_disposition_id"].isin(DEATH_HOSPICE_CODES)]
record("3. Remove deaths and hospice discharges", df, "discharge codes 11, 13, 14, 19, 20, 21")

# 5. Keep first recorded stay per patient (independence for statistical tests)
df = df.sort_values("encounter_id").drop_duplicates("patient_nbr", keep="first")
record("4. Keep first stay per patient", df)

# 6. Decode ID columns with the mapping file
maps, current = {}, None
with open(RAW / "IDS_mapping.csv", encoding="utf-8") as fh:
    mapping_lines = fh.read().splitlines()
for line in mapping_lines:
    line = line.strip()
    if not line or line == ",":
        continue
    key, _, label = line.partition(",")
    if key.endswith("_id"):
        current = key
        maps[current] = {}
    elif current and key.isdigit():
        maps[current][int(key)] = label.strip().strip('"')
for col, mapping in maps.items():
    df[col.replace("_id", "")] = df[col].map(mapping)

# 7. Group admission source and discharge destination into readable categories
def group_source(x):
    if x == 7:
        return "Emergency room"
    if x in (1, 2, 3):
        return "Referral"
    if x in (4, 5, 6, 10, 18, 22, 25, 26):
        return "Transfer"
    return "Other or unknown"


def group_discharge(x):
    if x == 1:
        return "Home"
    if x in (6, 8):
        return "Home with home health"
    if x in (3, 4, 24):
        return "Nursing facility"
    if x in (2, 5, 9, 10, 12, 15, 16, 17, 22, 23, 27, 28, 29, 30):
        return "Other inpatient or rehab"
    if x == 7:
        return "Left against advice"
    return "Other or unknown"


df["admission_source_group"] = df["admission_source_id"].apply(group_source)
df["discharge_group"] = df["discharge_disposition_id"].apply(group_discharge)

# 8. Group primary diagnosis (ICD-9) into clinical categories
def icd9_group(code):
    if pd.isna(code):
        return "Missing"
    code = str(code)
    if code.startswith(("V", "E")):
        return "Other"
    v = float(code)
    if int(v) == 250:
        return "Diabetes"
    if 390 <= v <= 459 or int(v) == 785:
        return "Circulatory"
    if 460 <= v <= 519 or int(v) == 786:
        return "Respiratory"
    if 520 <= v <= 579 or int(v) == 787:
        return "Digestive"
    if 800 <= v <= 999:
        return "Injury"
    if 710 <= v <= 739:
        return "Musculoskeletal"
    if 580 <= v <= 629 or int(v) == 788:
        return "Genitourinary"
    if 140 <= v <= 239:
        return "Neoplasms"
    return "Other"


df["primary_diagnosis_group"] = df["diag_1"].apply(icd9_group)

# 9. Derived fields
df["readmitted_30"] = (df["readmitted"] == "<30").astype(int)
df["age_band"] = df["age"].str.strip("[)").str.replace("-", " to ")
df["age_mid"] = df["age"].str.extract(r"\[(\d+)-").astype(int) + 5
df["prior_visits"] = df["number_outpatient"] + df["number_emergency"] + df["number_inpatient"]
df["a1c_tested"] = (df["A1Cresult"] != "Not tested").astype(int)
df["race"] = df["race"].fillna("Unknown")
med_cols = ["metformin", "repaglinide", "nateglinide", "chlorpropamide", "glimepiride",
            "acetohexamide", "glipizide", "glyburide", "tolbutamide", "pioglitazone",
            "rosiglitazone", "acarbose", "miglitol", "troglitazone", "tolazamide",
            "examide", "citoglipton", "insulin", "glyburide-metformin", "glipizide-metformin",
            "glimepiride-pioglitazone", "metformin-rosiglitazone", "metformin-pioglitazone"]
df["med_changes"] = (df[med_cols].isin(["Up", "Down"])).sum(axis=1)
record("5. Decode codes and add derived fields", df, "12 new fields")

df.to_csv(PROCESSED / "readmissions_clean.csv", index=False)
pd.DataFrame(log).to_csv(PROCESSED / "cleaning_log.csv", index=False)
print("\nSaved readmissions_clean.csv with", df.shape[1], "columns")
