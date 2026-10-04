# Reducing 30-Day Readmissions: A Healthcare Analytics Case Study

A retrospective healthcare analytics case study demonstrating risk stratification and capacity-planning methods using historical public data.

Meridian Health Network is a fictional case organisation. Its stakeholder discovery exercise is simulated, and no real interviews took place. Financial assumptions are illustrative.

> **Not for clinical use.** The risk model is an analytical prototype for portfolio demonstration. It has not been clinically validated, certified or approved for patient-care decisions.

## What the project covers

- Stakeholder discovery and requirements traceability
- Data quality assessment and cleaning of 101,766 hospital encounters
- Descriptive statistics and FDR-adjusted exploratory tests
- Logistic regression risk model with cross-validation, calibration, PR-AUC and Brier score
- Follow-up capacity scenarios and a hypothetical business case
- Subgroup performance checks by sex, race and age, with a fairness root-cause analysis
- HbA1c testing variation by subgroup, using z-scores and a funnel plot

## Read it first

- [Full case study (PDF)](docs/Readmissions-Case-Study.pdf)
- [Interactive dashboard and capacity explorer](https://chigozie-nkwopara.netlify.app/readmissions-case-study)
- [Power BI report](https://github.com/Ghenomenon/readmissions-powerbi)
- [What changed between versions](CHANGELOG.md)

Headline results on the 20,997 test patients: AUC 0.649. Following up the highest-risk 20% (4,200 patients) captures 699 of 1,886 readmissions, a recall of 37.1% and precision of 16.6%.

## How to run it

1. Download the dataset from the [UCI Machine Learning Repository](https://doi.org/10.24432/C5230J).
2. Unzip it and place `diabetic_data.csv` and `IDS_mapping.csv` in `data/raw/`.
3. Install the requirements and run the pipeline:

```
pip install -r requirements.txt
python run_all.py
```

The pipeline rebuilds the cleaned data, every chart and table, and the Power BI dashboard data in `outputs/powerbi/dashboard_data/`. Point the Power BI `DataFolder` parameter at that folder. Raw data and row-level outputs stay on your machine and are not part of this repository.

## Structure

| Path | Contents |
| --- | --- |
| `run_all.py` | Runs the eight steps in order |
| `src/01_clean_data.py` | Cleaning and derived fields |
| `src/02_visualise_cleaning.py` | Charts 01 to 03 |
| `src/03_descriptive_stats.py` | Charts 04 to 12 and summary tables |
| `src/04_analysis.py` | Statistical tests, risk model, charts 13 to 17 |
| `src/05_model_evaluation.py` | Calibration, capacity scenarios, subgroup checks, business case, charts 18 and 19 |
| `src/06_further_analysis.py` | HbA1c testing variation, correlations, fairness root cause, charts 20 and 21 |
| `src/07_doc_figures.py` | Combined figures used in the written report |
| `src/08_powerbi_export.py` | The eight CSV files the Power BI dashboard loads, with the same groupings as the report |
| `src/style.py` | Shared paths and chart style |
| `outputs/figures/` | Charts |
| `outputs/tables/` | Aggregated result tables |
| `outputs/web/` | Aggregate files used by the portfolio dashboard |
| `docs/` | The full case study as a PDF |

## Data source and licence

This project uses the [Diabetes 130-US Hospitals for Years 1999–2008](https://doi.org/10.24432/C5230J) dataset by John Clore, Krzysztof Cios, Jon DeShazo and Beata Strack, UCI Machine Learning Repository, DOI 10.24432/C5230J, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The source data were cleaned, recoded, grouped and transformed for this analysis. UCI and the dataset creators do not endorse this project or the fictional Meridian Health Network scenario.

Citation: Clore, J., Cios, K., DeShazo, J., and Strack, B. (2014). Diabetes 130-US Hospitals for Years 1999–2008 [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5230J

## Licence

Code: MIT (see `LICENSE`). Data: CC BY 4.0, as above.

## Author

Chigozie Nkwopara · [GitHub](https://github.com/Ghenomenon) · [Portfolio](https://chigozie-nkwopara.netlify.app)
