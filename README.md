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

## Analysis

After data collection, run `analysis.R` to:
- Compare task completion rates between Group A and Group B (Chi-square / Mann-Whitney U)
- Compare total time between groups (Welch t-test)
- Visualise per-task completion rates and time distributions