# Changelog

## 4 October 2026, evening: results reconciled with the dashboard and portfolio

The earlier package and the live dashboard came from two slightly different pipeline versions. This release replaces the package with the one pipeline that now produces the report, the Power BI data and the portfolio site.

What changed and why:

- Discharge codes 9, 12, 16 and 17 are now grouped with other inpatient care and rehab. The earlier version kept them as a separate group with only 22 patients, too few to estimate reliably.
- Rare admission types (newborn, trauma centre, not mapped, not available) are grouped as "Other or unknown". Missing primary diagnoses join "Other".
- The model is unchanged. The regrouping moves the 20% scenario from 697 to 699 captured readmissions (1,189 to 1,187 missed) and recall from 36.96% to 37.06%. AUC moves from 0.6492 to 0.6494. The base-case net benefit moves from $21,494 to $21,613 per 1,000 discharges.
- Added `src/08_powerbi_export.py`. It writes the Power BI data and the aggregate files behind the portfolio dashboard, so all three outputs come from one run.
- The report PDF in `docs/` is the current 23-page version.

## 4 October 2026, morning: publication revisions

- Corrected discharge categories and regenerated model, capacity, financial and subgroup outputs.
- Clarified lowest-ID index selection and hospice exclusion.
- Distinguished absent glucose testing from ordinary missing data.
- Removed unsupported collinearity, causal fairness and typical-performance claims.
- Defined average precision, categorical reference levels and cross-validation scope.
- Added Wilson confidence intervals for subgroup recall and descriptive funnel limitations.
- Qualified hypothetical costs, prevention assumptions and clinical recommendations.
- Removed unsupported dashboard and SQL deliverable claims.
- Added Pillow dependency, MIT code licence and editable report narrative.
- Retained CC BY attribution and conditional clinical-safety disclosures.
- Rebuilt and visually checked the 22-page PDF.

Validation: the full seven-step pipeline completed against the UCI source extract. Raw and row-level derivative data are excluded from this package.
