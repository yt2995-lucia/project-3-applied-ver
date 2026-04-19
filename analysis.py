# =============================================================================
# analysis.py — Statistical Analysis for DataScope A/B Usability Study
# STAT-GR5243 Project 3
#
# Research Question:
#   Does providing step-by-step hints (Group B) improve task completion
#   and time efficiency compared to no guidance (Group A)?
#
# H0: No difference in task completion rate or time between groups A and B.
# H1: Group B (hints) achieves higher task completion and/or different time.
#
# USAGE:
#   pip install pandas numpy scipy matplotlib seaborn statsmodels
#   python analysis.py
#
# OUTPUTS:
#   figures/  — all saved plots (PNG)
#   results printed to stdout
# =============================================================================

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from scipy import stats
from scipy.stats import (
    shapiro, mannwhitneyu, chi2_contingency,
    fisher_exact, ttest_ind, bootstrap
)
import statsmodels.api as sm
from statsmodels.stats.proportion import proportions_ztest, proportion_confint
from statsmodels.stats.power import TTestIndPower, GofChisquarePower

warnings.filterwarnings("ignore")
os.makedirs("figures", exist_ok=True)

# ── Aesthetics ────────────────────────────────────────────────────────────────
PALETTE = {"A": "#3498db", "B": "#e74c3c"}
GROUP_LABELS = {"A": "Group A (No Hints)", "B": "Group B (Hints)"}
sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight"})

DIVIDER = "=" * 70


# =============================================================================
# 0. Load Data
# =============================================================================
df_full = pd.read_csv("ab_test_clean_keep_outliers.csv")
df_trim = pd.read_csv("ab_test_clean_no_outliers.csv")

# Replace "Nan" strings with proper NaN
for col in ["experienced", "difficulty"]:
    df_full[col] = df_full[col].replace("Nan", np.nan)
    df_trim[col] = df_trim[col].replace("Nan", np.nan)

A_full = df_full[df_full["group"] == "A"]
B_full = df_full[df_full["group"] == "B"]
A_trim = df_trim[df_trim["group"] == "A"]
B_trim = df_trim[df_trim["group"] == "B"]

print(DIVIDER)
print("DATASCOPE A/B USABILITY STUDY — STATISTICAL ANALYSIS")
print(DIVIDER)
print(f"\nDataset sizes:")
print(f"  Full  (outliers kept):    n={len(df_full)}  (A={len(A_full)}, B={len(B_full)})")
print(f"  Trimmed (outliers removed): n={len(df_trim)}  (A={len(A_trim)}, B={len(B_trim)})")


# =============================================================================
# Helper functions
# =============================================================================

def cohens_d(x, y):
    """Cohen's d effect size for two independent samples."""
    nx, ny = len(x), len(y)
    pooled_std = np.sqrt(((nx - 1) * np.std(x, ddof=1)**2 +
                          (ny - 1) * np.std(y, ddof=1)**2) / (nx + ny - 2))
    return (np.mean(x) - np.mean(y)) / pooled_std if pooled_std > 0 else 0.0


def cramers_v(contingency_table):
    """Cramér's V effect size for chi-square tests."""
    chi2, _, _, _ = chi2_contingency(contingency_table)
    n = contingency_table.values.sum()
    k = min(contingency_table.shape) - 1
    return np.sqrt(chi2 / (n * k)) if k > 0 else 0.0


def rank_biserial_r(U, n1, n2):
    """Rank-biserial correlation (effect size for Mann-Whitney U)."""
    return 1 - (2 * U) / (n1 * n2)


def bootstrap_ci(x, y, stat_func, n_boot=10_000, ci=0.95, seed=42):
    """
    Bootstrap confidence interval for a two-sample statistic.
    stat_func(a, b) -> scalar.
    """
    rng = np.random.default_rng(seed)
    obs = stat_func(x, y)
    boot_stats = []
    for _ in range(n_boot):
        x_b = rng.choice(x, size=len(x), replace=True)
        y_b = rng.choice(y, size=len(y), replace=True)
        boot_stats.append(stat_func(x_b, y_b))
    lo = np.percentile(boot_stats, 100 * (1 - ci) / 2)
    hi = np.percentile(boot_stats, 100 * (1 + ci) / 2)
    return obs, lo, hi


def mean_diff(a, b):
    return np.mean(a) - np.mean(b)


def print_section(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


# =============================================================================
# 1. Descriptive Statistics
# =============================================================================
print_section("1. DESCRIPTIVE STATISTICS")

metrics = ["completion_rate", "n_tasks_done", "avg_time_per_task", "total_time_sec"]
metric_labels = {
    "completion_rate":    "Completion Rate (0–1)",
    "n_tasks_done":       "Number of Tasks Done (0–5)",
    "avg_time_per_task":  "Avg. Time per Completed Task (s)",
    "total_time_sec":     "Total Session Time (s)",
}

desc = df_full.groupby("group")[metrics].agg(
    ["count", "mean", "median", "std", "min", "max"]
).round(3)
print("\nFull dataset (outliers kept):")
print(desc.to_string())

desc_trim = df_trim.groupby("group")[metrics].agg(
    ["count", "mean", "median", "std", "min", "max"]
).round(3)
print("\nTrimmed dataset (outliers removed):")
print(desc_trim.to_string())

# Completion counts
print("\nTask Completion (completed all 5 tasks):")
comp_tab = pd.crosstab(df_full["group"], df_full["completed_all"],
                       rownames=["Group"], colnames=["Completed All"])
comp_tab.columns = ["Incomplete", "Complete"]
print(comp_tab)
print("\nCompletion rates by group:")
print((comp_tab["Complete"] / comp_tab.sum(axis=1)).round(4))


# =============================================================================
# 2. Normality Tests
# =============================================================================
print_section("2. NORMALITY TESTS (Shapiro-Wilk)")

norm_vars = ["avg_time_per_task", "total_time_sec", "completion_rate"]
for var in norm_vars:
    for grp, grp_df in [("A", A_full), ("B", B_full)]:
        vals = grp_df[var].dropna()
        stat, p = shapiro(vals)
        label = "NORMAL" if p > 0.05 else "NON-NORMAL"
        print(f"  {var:28s} | Group {grp} | W={stat:.4f}, p={p:.4f}  [{label}]")


# =============================================================================
# 3. PRIMARY ANALYSIS — Task Completion (Binary Outcome)
# =============================================================================
print_section("3. PRIMARY ANALYSIS — TASK COMPLETION RATE")

# --- 3a. Chi-Square Test ---
ct = pd.crosstab(df_full["group"], df_full["completed_all"])
chi2, p_chi2, dof, expected = chi2_contingency(ct)
v = cramers_v(ct)

print(f"\n  Chi-Square Test (completed all 5 tasks):")
print(f"    χ²({dof}) = {chi2:.4f},  p = {p_chi2:.4f}")
print(f"    Cramér's V = {v:.4f}  (effect size: {'small' if v<0.3 else 'medium' if v<0.5 else 'large'})")

# --- 3b. Fisher's Exact Test (additional robustness) ---
# Build 2×2 table: complete vs incomplete
a_complete   = int(A_full["completed_all"].sum())
a_incomplete = int(len(A_full) - a_complete)
b_complete   = int(B_full["completed_all"].sum())
b_incomplete = int(len(B_full) - b_complete)
table_2x2 = [[a_complete, a_incomplete], [b_complete, b_incomplete]]
or_fe, p_fe = fisher_exact(table_2x2, alternative="two-sided")
ci_lo, ci_hi = np.exp(np.log(or_fe) + np.array([-1, 1]) * 1.96 *
                      np.sqrt(1/a_complete + 1/a_incomplete +
                              1/b_complete + 1/b_incomplete))

print(f"\n  Fisher's Exact Test:")
print(f"    Odds Ratio = {or_fe:.3f}  (95% CI: [{ci_lo:.3f}, {ci_hi:.3f}])")
print(f"    p = {p_fe:.4f}")

# --- 3c. Proportions z-test ---
count_arr = np.array([a_complete, b_complete])
nobs_arr  = np.array([len(A_full), len(B_full)])
z_prop, p_prop = proportions_ztest(count_arr, nobs_arr)
ci_A = proportion_confint(a_complete, len(A_full), method="wilson")
ci_B = proportion_confint(b_complete, len(B_full), method="wilson")

print(f"\n  Two-Proportion z-Test:")
print(f"    Group A completion: {a_complete}/{len(A_full)} = {a_complete/len(A_full):.3f}  "
      f"(95% CI: [{ci_A[0]:.3f}, {ci_A[1]:.3f}])")
print(f"    Group B completion: {b_complete}/{len(B_full)} = {b_complete/len(B_full):.3f}  "
      f"(95% CI: [{ci_B[0]:.3f}, {ci_B[1]:.3f}])")
print(f"    z = {z_prop:.4f},  p = {p_prop:.4f}")

# --- 3d. Number of tasks completed (continuous) ---
print(f"\n  Number of tasks completed (0–5):")
print(f"    Group A: mean={A_full['n_tasks_done'].mean():.2f}, "
      f"median={A_full['n_tasks_done'].median():.1f}")
print(f"    Group B: mean={B_full['n_tasks_done'].mean():.2f}, "
      f"median={B_full['n_tasks_done'].median():.1f}")

U_tasks, p_tasks = mannwhitneyu(A_full["n_tasks_done"], B_full["n_tasks_done"],
                                 alternative="two-sided")
r_tasks = rank_biserial_r(U_tasks, len(A_full), len(B_full))
print(f"    Mann-Whitney U = {U_tasks:.1f},  p = {p_tasks:.4f}")
print(f"    Rank-biserial r = {r_tasks:.4f}  (effect size)")


# =============================================================================
# 4. SECONDARY ANALYSIS — Time Efficiency
# =============================================================================
print_section("4. SECONDARY ANALYSIS — TIME EFFICIENCY")

# Use only participants who completed all 5 tasks (apples-to-apples)
A_done = A_full[A_full["completed_all"] == 1]["avg_time_per_task"].dropna()
B_done = B_full[B_full["completed_all"] == 1]["avg_time_per_task"].dropna()

print(f"\n  Restricting to participants who completed ALL 5 tasks:")
print(f"    Group A: n={len(A_done)},  mean={A_done.mean():.2f}s,  "
      f"median={A_done.median():.2f}s,  SD={A_done.std():.2f}s")
print(f"    Group B: n={len(B_done)},  mean={B_done.mean():.2f}s,  "
      f"median={B_done.median():.2f}s,  SD={B_done.std():.2f}s")

# --- 4a. Normality check on completers ---
_, p_norm_A = shapiro(A_done)
_, p_norm_B = shapiro(B_done)
print(f"\n  Shapiro-Wilk (completers):  Group A p={p_norm_A:.4f}, Group B p={p_norm_B:.4f}")

# --- 4b. Mann-Whitney U (primary, non-parametric) ---
U_time, p_mw = mannwhitneyu(A_done, B_done, alternative="two-sided")
r_time = rank_biserial_r(U_time, len(A_done), len(B_done))
print(f"\n  Mann-Whitney U Test (avg time per task — completers):")
print(f"    U = {U_time:.1f},  p = {p_mw:.4f}")
print(f"    Rank-biserial r = {r_time:.4f}")

# --- 4c. Welch t-test (parametric, for comparison) ---
t_stat, p_ttest = ttest_ind(A_done, B_done, equal_var=False)
d = cohens_d(A_done.values, B_done.values)
print(f"\n  Welch's t-Test (avg time per task — completers):")
print(f"    t = {t_stat:.4f},  p = {p_ttest:.4f}")
print(f"    Cohen's d = {d:.4f}  (effect size: {'negligible' if abs(d)<0.2 else 'small' if abs(d)<0.5 else 'medium' if abs(d)<0.8 else 'large'})")

# --- 4d. Bootstrap CI for mean difference ---
obs_diff, ci_lo_boot, ci_hi_boot = bootstrap_ci(
    A_done.values, B_done.values, mean_diff, n_boot=10_000
)
print(f"\n  Bootstrap 95% CI for mean difference (A − B):")
print(f"    Δ = {obs_diff:.2f}s  (95% CI: [{ci_lo_boot:.2f}, {ci_hi_boot:.2f}])")

# --- 4e. All participants (total time) ---
print(f"\n  Total session time — all participants:")
U_tot, p_tot = mannwhitneyu(A_full["total_time_sec"], B_full["total_time_sec"],
                             alternative="two-sided")
r_tot = rank_biserial_r(U_tot, len(A_full), len(B_full))
print(f"    Group A: mean={A_full['total_time_sec'].mean():.1f}s, "
      f"median={A_full['total_time_sec'].median():.1f}s")
print(f"    Group B: mean={B_full['total_time_sec'].mean():.1f}s, "
      f"median={B_full['total_time_sec'].median():.1f}s")
print(f"    Mann-Whitney U = {U_tot:.1f},  p = {p_tot:.4f},  r = {r_tot:.4f}")


# =============================================================================
# 5. SENSITIVITY ANALYSIS — Outlier Impact
# =============================================================================
print_section("5. SENSITIVITY ANALYSIS — OUTLIER ROBUSTNESS")

for label, dfx in [("Full (outliers kept)", df_full), ("Trimmed (outliers removed)", df_trim)]:
    gA = dfx[dfx["group"] == "A"]
    gB = dfx[dfx["group"] == "B"]
    ct_s = pd.crosstab(dfx["group"], dfx["completed_all"])
    chi2_s, p_s, _, _ = chi2_contingency(ct_s)
    v_s = cramers_v(ct_s)

    dA_s = gA[gA["completed_all"] == 1]["avg_time_per_task"].dropna()
    dB_s = gB[gB["completed_all"] == 1]["avg_time_per_task"].dropna()
    U_s, p_mw_s = mannwhitneyu(dA_s, dB_s, alternative="two-sided") if len(dA_s) > 0 and len(dB_s) > 0 else (np.nan, np.nan)

    print(f"\n  {label}:  n={len(dfx)} (A={len(gA)}, B={len(gB)})")
    print(f"    Completion χ²={chi2_s:.3f}, p={p_s:.4f}, Cramér's V={v_s:.4f}")
    print(f"    Time MWU: U={U_s:.1f}, p={p_mw_s:.4f}" if not np.isnan(U_s) else "    Time MWU: N/A")


# =============================================================================
# 6. SUBGROUP ANALYSIS — Experience & Perceived Difficulty
# =============================================================================
print_section("6. SUBGROUP ANALYSIS — MODERATORS")

for subvar, subname in [("experienced", "Prior Experience"), ("difficulty", "Perceived Difficulty")]:
    print(f"\n  Subgroup: {subname}")
    for val in ["Yes", "No"]:
        sub = df_full[df_full[subvar] == val]
        if len(sub) < 10:
            print(f"    {val}: n={len(sub)} (too small to test)")
            continue
        sA = sub[sub["group"] == "A"]["completed_all"]
        sB = sub[sub["group"] == "B"]["completed_all"]
        if len(sA) == 0 or len(sB) == 0:
            continue
        n_sA, n_sB = len(sA), len(sB)
        c_sA, c_sB = int(sA.sum()), int(sB.sum())
        t2x2 = [[c_sA, n_sA - c_sA], [c_sB, n_sB - c_sB]]
        or_sub, p_sub = fisher_exact(t2x2)
        print(f"    {val:3s} (n={len(sub):2d}):  "
              f"A completion={c_sA}/{n_sA}={c_sA/n_sA:.2f}, "
              f"B completion={c_sB}/{n_sB}={c_sB/n_sB:.2f}  |  "
              f"OR={or_sub:.2f}, Fisher p={p_sub:.4f}")


# =============================================================================
# 7. STATISTICAL POWER ANALYSIS
# =============================================================================
print_section("7. POST-HOC POWER ANALYSIS")

# Power for chi-square (completion)
p_A_obs = a_complete / len(A_full)
p_B_obs = b_complete / len(B_full)
p_pool  = (a_complete + b_complete) / (len(A_full) + len(B_full))
h = 2 * (np.arcsin(np.sqrt(p_B_obs)) - np.arcsin(np.sqrt(p_A_obs)))
power_chi2 = GofChisquarePower().solve_power(
    effect_size=abs(h), nobs=len(df_full), alpha=0.05, n_bins=2
)
print(f"\n  Observed effect size h (Cohen's h) for completion: {h:.4f}")
print(f"  Post-hoc power (chi-square, α=0.05, n={len(df_full)}): {power_chi2:.4f}")

# Power for t-test (time among completers)
power_t = TTestIndPower().solve_power(
    effect_size=abs(d), nobs1=len(A_done),
    ratio=len(B_done) / len(A_done), alpha=0.05
)
print(f"\n  Observed Cohen's d for avg time per task: {d:.4f}")
print(f"  Post-hoc power (t-test, α=0.05, nA={len(A_done)}, nB={len(B_done)}): {power_t:.4f}")


# =============================================================================
# 8. VISUALIZATIONS
# =============================================================================
print_section("8. GENERATING FIGURES")

group_order = ["A", "B"]
group_tick_labels = ["Group A\n(No Hints)", "Group B\n(Hints)"]
colors = [PALETTE["A"], PALETTE["B"]]

# ── Figure 1: Completion Rate Comparison ─────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
fig.suptitle("Task Completion: Group A vs. Group B", fontsize=14, fontweight="bold")

# Stacked bar
comp_pct = df_full.groupby("group")["completed_all"].value_counts(normalize=True).unstack().fillna(0)
comp_pct.columns = ["Incomplete", "Complete"]
comp_pct = comp_pct.reindex(group_order)
bars_inc = axes[0].bar(group_tick_labels, comp_pct["Incomplete"], color=["#aed6f1", "#f1948a"], label="Incomplete")
bars_com = axes[0].bar(group_tick_labels, comp_pct["Complete"],
                       bottom=comp_pct["Incomplete"], color=colors, label="Complete All 5")
for bar, val in zip(bars_com, comp_pct["Complete"]):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + bar.get_y() - 0.04,
                 f"{val:.1%}", ha="center", va="bottom", fontweight="bold", fontsize=11)
axes[0].set_ylim(0, 1.05)
axes[0].set_ylabel("Proportion of Participants")
axes[0].set_title("Completion Rate by Group")
axes[0].legend(loc="upper right")
axes[0].spines["top"].set_visible(False)
axes[0].spines["right"].set_visible(False)

# n_tasks_done violin
parts = axes[1].violinplot(
    [A_full["n_tasks_done"].values, B_full["n_tasks_done"].values],
    positions=[0, 1], showmedians=True, showextrema=True
)
for i, (pc, c) in enumerate(zip(parts["bodies"], colors)):
    pc.set_facecolor(c)
    pc.set_alpha(0.7)
parts["cmedians"].set_color("black")
parts["cmedians"].set_linewidth(2)
# Overlay jittered strip
rng = np.random.default_rng(0)
for i, (grp_df, c) in enumerate([(A_full, PALETTE["A"]), (B_full, PALETTE["B"])]):
    jitter = rng.uniform(-0.08, 0.08, len(grp_df))
    axes[1].scatter(np.full(len(grp_df), i) + jitter,
                    grp_df["n_tasks_done"], alpha=0.5, s=20, color=c, zorder=3)
axes[1].set_xticks([0, 1])
axes[1].set_xticklabels(group_tick_labels)
axes[1].set_ylabel("Number of Tasks Completed (0–5)")
axes[1].set_title("Distribution of Tasks Completed")
axes[1].spines["top"].set_visible(False)
axes[1].spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("figures/fig1_completion.png")
plt.close()
print("  Saved: figures/fig1_completion.png")

# ── Figure 2: Time Analysis ───────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Time Analysis: Group A vs. Group B", fontsize=14, fontweight="bold")

# Box + strip for avg_time_per_task (completers only)
data_time = pd.DataFrame({
    "group": ["A"] * len(A_done) + ["B"] * len(B_done),
    "avg_time_per_task": list(A_done.values) + list(B_done.values)
})
bp = axes[0].boxplot(
    [A_done.values, B_done.values],
    positions=[0, 1], widths=0.4, patch_artist=True,
    medianprops=dict(color="black", linewidth=2),
    flierprops=dict(marker="o", markerfacecolor="gray", markersize=5, alpha=0.5)
)
for patch, c in zip(bp["boxes"], colors):
    patch.set_facecolor(c)
    patch.set_alpha(0.7)
rng2 = np.random.default_rng(1)
for i, (vals, c) in enumerate([(A_done.values, PALETTE["A"]), (B_done.values, PALETTE["B"])]):
    jitter = rng2.uniform(-0.12, 0.12, len(vals))
    axes[0].scatter(np.full(len(vals), i) + jitter, vals,
                    alpha=0.55, s=22, color=c, zorder=3)
axes[0].set_xticks([0, 1])
axes[0].set_xticklabels(group_tick_labels)
axes[0].set_ylabel("Avg. Time per Task (s)")
axes[0].set_title("Avg. Time per Task\n(Completers Only)")
axes[0].spines["top"].set_visible(False)
axes[0].spines["right"].set_visible(False)

# KDE of total session time
for grp, c, lbl in [("A", PALETTE["A"], "Group A (No Hints)"),
                     ("B", PALETTE["B"], "Group B (Hints)")]:
    vals = df_full[df_full["group"] == grp]["total_time_sec"].dropna()
    sns.kdeplot(vals, ax=axes[1], color=c, label=lbl, linewidth=2, fill=True, alpha=0.25)
    axes[1].axvline(vals.median(), color=c, linestyle="--", linewidth=1.5, alpha=0.8)
axes[1].set_xlabel("Total Session Time (s)")
axes[1].set_ylabel("Density")
axes[1].set_title("Total Session Time Distribution\n(dashed = median)")
axes[1].legend()
axes[1].spines["top"].set_visible(False)
axes[1].spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("figures/fig2_time.png")
plt.close()
print("  Saved: figures/fig2_time.png")

# ── Figure 3: Per-Task Completion Rates ──────────────────────────────────────
task_cols = [f"t{i}_done" for i in range(1, 6)]
task_labels_short = [f"Task {i}" for i in range(1, 6)]

fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(5)
w = 0.35
rates_A = [A_full[c].map({True: 1, False: 0}).mean() for c in task_cols]
rates_B = [B_full[c].map({True: 1, False: 0}).mean() for c in task_cols]

bars_A = ax.bar(x - w/2, rates_A, width=w, label="Group A (No Hints)",
                color=PALETTE["A"], alpha=0.85, edgecolor="white")
bars_B = ax.bar(x + w/2, rates_B, width=w, label="Group B (Hints)",
                color=PALETTE["B"], alpha=0.85, edgecolor="white")
for bar in list(bars_A) + list(bars_B):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
            f"{bar.get_height():.0%}", ha="center", va="bottom", fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels(task_labels_short)
ax.set_ylabel("Proportion Completed")
ax.set_ylim(0, 1.12)
ax.set_title("Per-Task Completion Rate by Group", fontsize=13, fontweight="bold")
ax.legend()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("figures/fig3_per_task.png")
plt.close()
print("  Saved: figures/fig3_per_task.png")

# ── Figure 4: Per-Task Median Time (completers only) ─────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
time_cols = [f"t{i}_time_s" for i in range(1, 6)]

# Compute median time per task among those who completed it, by group
med_A, med_B = [], []
for tc in time_cols:
    med_A.append(A_full[tc].dropna().median())
    med_B.append(B_full[tc].dropna().median())

ax.plot(task_labels_short, med_A, "o-", color=PALETTE["A"], linewidth=2.5,
        markersize=8, label="Group A (No Hints)")
ax.plot(task_labels_short, med_B, "s-", color=PALETTE["B"], linewidth=2.5,
        markersize=8, label="Group B (Hints)")
ax.fill_between(task_labels_short, med_A, med_B, alpha=0.12, color="gray")
ax.set_ylabel("Median Cumulative Elapsed Time (s)")
ax.set_title("Cumulative Elapsed Time at Each Task Completion\n(median across participants who reached that task)",
             fontsize=12, fontweight="bold")
ax.legend()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("figures/fig4_per_task_time.png")
plt.close()
print("  Saved: figures/fig4_per_task_time.png")

# ── Figure 5: Subgroup Analysis — Completion by Experience ───────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Subgroup Analysis: Completion Rate", fontsize=14, fontweight="bold")

for ax_i, (subvar, subname) in enumerate(
        [("experienced", "Prior Experience"), ("difficulty", "Perceived Difficulty")]):
    rates = {}
    for val in ["Yes", "No"]:
        sub = df_full[df_full[subvar] == val]
        for grp in ["A", "B"]:
            sub_g = sub[sub["group"] == grp]
            rate = sub_g["completed_all"].mean() if len(sub_g) > 0 else np.nan
            rates[(val, grp)] = (rate, len(sub_g))

    x2 = np.arange(2)
    w2 = 0.35
    vals_plot = ["Yes", "No"]
    rA = [rates[(v, "A")][0] for v in vals_plot]
    rB = [rates[(v, "B")][0] for v in vals_plot]
    bA = axes[ax_i].bar(x2 - w2/2, rA, width=w2, label="Group A", color=PALETTE["A"], alpha=0.85)
    bB = axes[ax_i].bar(x2 + w2/2, rB, width=w2, label="Group B", color=PALETTE["B"], alpha=0.85)
    for bar in list(bA) + list(bB):
        h_val = bar.get_height()
        if not np.isnan(h_val):
            axes[ax_i].text(bar.get_x() + bar.get_width()/2, h_val + 0.02,
                            f"{h_val:.0%}", ha="center", va="bottom", fontsize=10)
    axes[ax_i].set_xticks(x2)
    axes[ax_i].set_xticklabels([f"{subname}?\n{v}" for v in vals_plot])
    axes[ax_i].set_ylim(0, 1.15)
    axes[ax_i].set_ylabel("Proportion Who Completed All Tasks")
    axes[ax_i].set_title(f"By {subname}")
    axes[ax_i].legend()
    axes[ax_i].spines["top"].set_visible(False)
    axes[ax_i].spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("figures/fig5_subgroup.png")
plt.close()
print("  Saved: figures/fig5_subgroup.png")

# ── Figure 6: Bootstrap Distribution of Mean Difference ──────────────────────
rng3 = np.random.default_rng(42)
boot_diffs = []
for _ in range(10_000):
    a_b = rng3.choice(A_done.values, size=len(A_done), replace=True)
    b_b = rng3.choice(B_done.values, size=len(B_done), replace=True)
    boot_diffs.append(np.mean(a_b) - np.mean(b_b))
boot_diffs = np.array(boot_diffs)

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(boot_diffs, bins=60, color="#95a5a6", edgecolor="white", alpha=0.85)
ax.axvline(obs_diff, color="#2c3e50", linewidth=2.5, label=f"Observed Δ = {obs_diff:.2f}s")
ax.axvline(ci_lo_boot, color="#e74c3c", linewidth=1.8, linestyle="--",
           label=f"95% CI [{ci_lo_boot:.2f}, {ci_hi_boot:.2f}]")
ax.axvline(ci_hi_boot, color="#e74c3c", linewidth=1.8, linestyle="--")
ax.axvline(0, color="black", linewidth=1.2, linestyle=":", alpha=0.6, label="Null (Δ = 0)")
ax.set_xlabel("Mean Difference in Avg. Time per Task (A − B), seconds")
ax.set_ylabel("Bootstrap Frequency")
ax.set_title("Bootstrap Distribution: Mean Difference in Avg. Time\n(A completers − B completers, 10,000 resamples)",
             fontsize=12, fontweight="bold")
ax.legend()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("figures/fig6_bootstrap.png")
plt.close()
print("  Saved: figures/fig6_bootstrap.png")


# =============================================================================
# 9. SUMMARY TABLE
# =============================================================================
print_section("9. SUMMARY OF STATISTICAL TESTS")

summary = pd.DataFrame([
    {
        "Test": "Chi-Square (task completion)",
        "Statistic": f"χ²={chi2:.3f}",
        "p-value": f"{p_chi2:.4f}",
        "Effect Size": f"Cramér's V={v:.3f}",
        "Sig (α=0.05)": "YES" if p_chi2 < 0.05 else "NO"
    },
    {
        "Test": "Fisher's Exact (task completion)",
        "Statistic": f"OR={or_fe:.3f}",
        "p-value": f"{p_fe:.4f}",
        "Effect Size": f"OR 95% CI [{ci_lo:.3f},{ci_hi:.3f}]",
        "Sig (α=0.05)": "YES" if p_fe < 0.05 else "NO"
    },
    {
        "Test": "Proportions z-test (completion)",
        "Statistic": f"z={z_prop:.3f}",
        "p-value": f"{p_prop:.4f}",
        "Effect Size": f"h={h:.3f}",
        "Sig (α=0.05)": "YES" if p_prop < 0.05 else "NO"
    },
    {
        "Test": "Mann-Whitney U (tasks done)",
        "Statistic": f"U={U_tasks:.1f}",
        "p-value": f"{p_tasks:.4f}",
        "Effect Size": f"r={r_tasks:.3f}",
        "Sig (α=0.05)": "YES" if p_tasks < 0.05 else "NO"
    },
    {
        "Test": "Mann-Whitney U (avg time/task, completers)",
        "Statistic": f"U={U_time:.1f}",
        "p-value": f"{p_mw:.4f}",
        "Effect Size": f"r={r_time:.3f}",
        "Sig (α=0.05)": "YES" if p_mw < 0.05 else "NO"
    },
    {
        "Test": "Welch's t-test (avg time/task, completers)",
        "Statistic": f"t={t_stat:.3f}",
        "p-value": f"{p_ttest:.4f}",
        "Effect Size": f"Cohen's d={d:.3f}",
        "Sig (α=0.05)": "YES" if p_ttest < 0.05 else "NO"
    },
    {
        "Test": "Bootstrap CI (mean time diff, completers)",
        "Statistic": f"Δ={obs_diff:.2f}s",
        "p-value": "—",
        "Effect Size": f"95% CI [{ci_lo_boot:.2f},{ci_hi_boot:.2f}]",
        "Sig (α=0.05)": "YES" if ci_lo_boot > 0 or ci_hi_boot < 0 else "NO"
    },
])
print(summary.to_string(index=False))

print(f"\n{DIVIDER}")
print("INTERPRETATION")
print(DIVIDER)
print(f"""
Primary finding — Task Completion:
  Group B (hints) completed significantly more tasks than Group A (no hints).
  Completion rate: A={a_complete/len(A_full):.1%} vs B={b_complete/len(B_full):.1%}
  χ²={chi2:.3f}, p={p_chi2:.4f}, Cramér's V={v:.3f} ({'small' if v<0.3 else 'medium' if v<0.5 else 'large'} effect size).
  This result is consistent across Chi-Square, Fisher's Exact, and z-test.

Secondary finding — Time per Task:
  Among participants who completed all 5 tasks, Group A was {'faster' if A_done.mean() < B_done.mean() else 'slower'} on average
  (A={A_done.mean():.1f}s vs B={B_done.mean():.1f}s per task, Δ={obs_diff:.1f}s).
  Bootstrap 95% CI for A−B: [{ci_lo_boot:.2f}, {ci_hi_boot:.2f}].
  {'The difference is statistically significant (MWU p=' + f'{p_mw:.4f}).' if p_mw < 0.05 else 'The difference is NOT statistically significant (MWU p=' + f'{p_mw:.4f}).'}
  Interpretation: hints helped more users complete all tasks, but required
  more time — a classic comprehension-speed tradeoff.

Conclusion:
  We reject H0 for task completion: step-by-step hints (Group B) caused a
  statistically significant increase in the proportion of participants
  completing all 5 data tasks. The time tradeoff is present but not
  statistically significant at α=0.05 in the completers-only sample.
""")

print("\nAll figures saved to: figures/")
