# Project 3 — DataScope A/B Usability Study

A between-subject A/B test comparing two UI designs of a data analysis interface.

- **Group A (Control):** No guidance — participants explore the interface independently  
- **Group B (Treatment):** Step-by-step hints shown at each task — guided experience

Participants complete 5 data tasks. Completion rate and time per task are automatically recorded to Google Sheets.

---

## Research Question

Does providing step-by-step guidance in a data analysis interface improve task completion rate and reduce time-on-task compared to an unguided interface?

---

## Tasks Given to Participants

| # | Task |
|---|------|
| 1 | View the first 10 rows of the dataset |
| 2 | Generate summary statistics for all columns |
| 3 | Remove the 'Species' column from the dataset |
| 4 | Create a histogram of Sepal.Length |
| 5 | Identify which columns contain missing values |

---

## Setup Instructions

### 1. Install R packages

```r
install.packages(c("shiny", "bslib", "shinyjs", "DT", "ggplot2", "dplyr", "httr", "jsonlite"))
```

### 2. Set up Google Sheets (for automatic data collection)

1. Create a new Google Sheet
2. Open **Extensions → Apps Script**
3. Paste the contents of `google_apps_script.js` into the editor
4. Click **Deploy → New Deployment → Web App**
   - Execute as: **Me**
   - Who has access: **Anyone**
5. Copy the deployment URL
6. In `app.R`, replace `YOUR_SCRIPT_ID_HERE` in the `SHEETS_URL` variable with your URL

### 3. Run the app

```r
shiny::runApp()
```

---

## Data Collected

Each submission records:

| Field | Description |
|-------|-------------|
| `session_id` | Random 8-character session identifier |
| `participant_id` | Entered by participant (e.g. P123) |
| `group` | A (no hints) or B (with hints) |
| `n_tasks_done` | Number of tasks completed (0–5) |
| `total_time_sec` | Total time from start to submission (seconds) |
| `t1_done` … `t5_done` | Whether each task was completed (TRUE/FALSE) |
| `t1_time_s` … `t5_time_s` | Seconds from start until each task completed |
| `timestamp` | Date and time of submission |

---

## Repository Structure

```
project-3-applied-ver/
├── app.R                                      # Shiny app (Groups A & B)
├── google_apps_script.js                      # Google Sheets logging endpoint
├── data_cleaning.py                           # Raw data cleaning script
├── analysis.py                                # Full statistical analysis script
├── AB testing Data Collection - Sheet1 (2).csv  # Raw data export from Google Sheets
├── ab_test_clean_keep_outliers.csv            # Cleaned data (all 97 records)
├── ab_test_clean_no_outliers.csv              # Cleaned data (outliers removed, n=93)
├── figures/                                   # Output plots from analysis.py
│   ├── fig1_completion.png
│   ├── fig2_time.png
│   ├── fig3_per_task.png
│   ├── fig4_per_task_time.png
│   ├── fig5_subgroup.png
│   └── fig6_bootstrap.png
├── report.tex                                 # Full LaTeX report (Overleaf)
└── README.md
```

---

## Analysis

### Step 1 — Clean the raw data

```bash
python data_cleaning.py
```

Reads the raw Google Sheets CSV, standardises columns, removes duplicates, validates task completion flags, detects time outliers (IQR method), and writes two output files:

- `ab_test_clean_keep_outliers.csv` — all 97 valid records (used for primary analysis)
- `ab_test_clean_no_outliers.csv` — 93 records with extreme session times removed (used for sensitivity analysis)

### Step 2 — Install Python dependencies

```bash
pip install pandas numpy scipy matplotlib seaborn statsmodels
```

### Step 3 — Run the statistical analysis

```bash
python analysis.py
```

This script runs the full analysis pipeline and saves all figures to `figures/`. It covers:

| Section | What it does |
|---------|-------------|
| Descriptive statistics | Mean, median, SD for completion rate, tasks done, and time by group |
| Normality tests | Shapiro-Wilk on all continuous outcomes → justifies non-parametric tests |
| Primary analysis | Chi-square, Fisher's exact, and proportions z-test on full-completion (binary); Mann-Whitney U on task count |
| Secondary analysis | Mann-Whitney U and Welch's t-test on avg time/task (completers only); bootstrap 95% CI |
| Sensitivity analysis | Repeats all tests on outlier-trimmed dataset to confirm robustness |
| Subgroup analysis | Fisher's exact within prior-experience and perceived-difficulty strata |
| Power analysis | Post-hoc power for both primary tests |

### Key Results

| Metric | Group A (No Hints) | Group B (Hints) | Result |
|--------|-------------------|-----------------|--------|
| Full completion rate | 42.3% (22/52) | 71.1% (32/45) | **p = 0.008**, Cramér's V = 0.268 |
| Median tasks done | 4.0 | 5.0 | MWU **p = 0.003**, r = 0.317 |
| Median avg time/task (completers) | 8.1s | 17.0s | MWU p = 0.096 (n.s.) |
| Median total session time | 40.5s | 66.0s | MWU **p = 0.016**, r = 0.286 |

Group B (guided) completed significantly more tasks. The time difference among completers was not statistically significant, reflecting a comprehension–speed tradeoff rather than inefficiency.