"""
Run the full readmission case study pipeline in order.

    python run_all.py
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
STEPS = [
    "01_clean_data.py",
    "02_visualise_cleaning.py",
    "03_descriptive_stats.py",
    "04_analysis.py",
    "05_model_evaluation.py",
    "06_further_analysis.py",
    "07_doc_figures.py",
    "08_powerbi_export.py",
]

for step in STEPS:
    print(f"\n=== {step} ===")
    result = subprocess.run([sys.executable, step], cwd=SRC)
    if result.returncode != 0:
        sys.exit(f"Stopped: {step} failed")

print("\nPipeline complete. Outputs are in data/processed and outputs/.")
