import pandas as pd
import numpy as np

# ==============================
# 1. Load the dataset
# ==============================
df = pd.read_csv("AB testing Data Collection - Sheet1 (2).csv")

# ==============================
# 2. Inspect the dataset
# ==============================
print("Shape of raw data:", df.shape)
print("\nColumn names:")
print(df.columns.tolist())

print("\nData types:")
print(df.dtypes)

print("\nFirst 5 rows:")
print(df.head())

# ==============================
# 3. Remove unnecessary columns
# ==============================
# Drop the unnamed timestamp column because it is not needed for analysis
if "Unnamed: 17" in df.columns:
    df = df.drop(columns=["Unnamed: 17"])

# ==============================
# 4. Rename columns for convenience
# ==============================
# Rename columns to simpler and cleaner names
df = df.rename(columns={
    "Experienced in data？": "experienced",
    "Difficult？": "difficulty"
})

# ==============================
# 5. Standardize string variables
# ==============================
# Clean up group labels by removing extra spaces and converting to uppercase
df["group"] = df["group"].astype(str).str.strip().str.upper()

# Convert group to categorical type
df["group"] = df["group"].astype("category")

# Standardize Yes/No responses
df["experienced"] = df["experienced"].astype(str).str.strip().str.title()
df["difficulty"] = df["difficulty"].astype(str).str.strip().str.title()

# Create numeric versions of Yes/No variables for later analysis
df["experienced_num"] = df["experienced"].map({"Yes": 1, "No": 0})
df["difficulty_num"] = df["difficulty"].map({"Yes": 1, "No": 0})

# ==============================
# 6. Check for duplicate rows
# ==============================
# Check duplicate participant IDs
duplicate_participants = df[df.duplicated(subset="participant_id", keep=False)]

print("\nDuplicate participant_id rows:")
print(duplicate_participants)

# Remove duplicated participant IDs if needed
# Keep the first occurrence only
df = df.drop_duplicates(subset="participant_id", keep="first")

# ==============================
# 7. Check missing values
# ==============================
print("\nMissing values by column:")
print(df.isna().sum())

# ==============================
# 8. Check task completion consistency
# ==============================
# Verify that if a task is marked incomplete, its time is usually missing
for i in range(1, 6):
    bad_rows = df[(df[f"t{i}_done"] == False) & (df[f"t{i}_time_s"].notna())]
    print(f"\nTask {i}: rows with done=False but time recorded = {len(bad_rows)}")

# Verify that if a task is marked complete, its time should not be missing
for i in range(1, 6):
    bad_rows = df[(df[f"t{i}_done"] == True) & (df[f"t{i}_time_s"].isna())]
    print(f"\nTask {i}: rows with done=True but missing time = {len(bad_rows)}")

# ==============================
# 9. Recalculate number of completed tasks
# ==============================
# Recompute n_tasks_done using the five task completion indicators
done_cols = [f"t{i}_done" for i in range(1, 6)]
df["tasks_done_check"] = df[done_cols].sum(axis=1)

# Compare original n_tasks_done with recalculated values
mismatch = df[df["n_tasks_done"] != df["tasks_done_check"]]

print("\nRows where n_tasks_done does not match the task indicators:")
print(mismatch[["participant_id", "n_tasks_done", "tasks_done_check"]])

# Replace n_tasks_done with the checked version
df["n_tasks_done"] = df["tasks_done_check"]

# ==============================
# 10. Create outcome variables for analysis
# ==============================
# Primary outcome: whether all 5 tasks were completed
df["completed_all"] = (df["n_tasks_done"] == 5).astype(int)

# Completion rate: proportion of completed tasks
df["completion_rate"] = df["n_tasks_done"] / 5

# Average time per completed task
df["avg_time_per_task"] = np.where(
    df["n_tasks_done"] > 0,
    df["total_time_sec"] / df["n_tasks_done"],
    np.nan
)

# ==============================
# 11. Check time variables
# ==============================
print("\nSummary statistics for total_time_sec:")
print(df["total_time_sec"].describe())

# Keep only rows with positive total time
df = df[df["total_time_sec"] > 0].copy()

# ==============================
# 12. Detect outliers in total_time_sec using IQR
# ==============================
Q1 = df["total_time_sec"].quantile(0.25)
Q3 = df["total_time_sec"].quantile(0.75)
IQR = Q3 - Q1

lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

print("\nOutlier bounds for total_time_sec:")
print("Lower bound:", lower_bound)
print("Upper bound:", upper_bound)

# Create two versions:
# df_clean_keep = keep all valid rows
# df_clean = remove time outliers
df_clean_keep = df.copy()

df_clean = df[
    (df["total_time_sec"] >= lower_bound) &
    (df["total_time_sec"] <= upper_bound)
].copy()

print("\nShape after removing time outliers:", df_clean.shape)

# ==============================
# 13. Final inspection
# ==============================
print("\nCleaned data preview:")
print(df_clean.head())

print("\nCleaned data types:")
print(df_clean.dtypes)

print("\nGroup counts:")
print(df_clean["group"].value_counts())

print("\nCompleted all tasks by group:")
print(pd.crosstab(df_clean["group"], df_clean["completed_all"]))

# ==============================
# 14. Save cleaned datasets
# ==============================
# Save the version with outliers kept
df_clean_keep.to_csv("ab_test_clean_keep_outliers.csv", index=False)

# Save the version with outliers removed
df_clean.to_csv("ab_test_clean_no_outliers.csv", index=False)

print("\nFiles saved:")
print("- ab_test_clean_keep_outliers.csv")
print("- ab_test_clean_no_outliers.csv")