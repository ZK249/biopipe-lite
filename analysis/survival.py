"""Survival analysis module."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test

from analysis import read_dataframe


def run_survival_analysis(
    input_path: str,
    output_dir: str,
    time_col: str = 'time',
    event_col: str = 'event',
    group_col: str = 'group'
) -> dict:
    """
    Run survival analysis on clinical data.
    
    Args:
        input_path: Path to data with time, event, and optionally group columns
        output_dir: Directory to save results
        time_col: Column name for survival time
        event_col: Column name for event indicator (1=event, 0=censored)
        group_col: Column name for grouping variable (optional)
    
    Returns:
        Dictionary with result paths and statistics
    """
    # Load data
    df = read_dataframe(input_path)
    
    # Validate required columns
    for col in [time_col, event_col]:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in data")
    
    # Basic statistics
    n_total = len(df)
    n_events = df[event_col].sum()
    n_censored = n_total - n_events
    
    os.makedirs(output_dir, exist_ok=True)
    
    results = {
        'n_total': n_total,
        'n_events': int(n_events),
        'n_censored': int(n_censored),
        'median_survival': None,
        'plot_paths': {}
    }
    
    # Overall survival curve
    kmf_overall = KaplanMeierFitter()
    kmf_overall.fit(df[time_col], df[event_col], label='Overall')
    results['median_survival'] = kmf_overall.median_survival_time_
    
    # Plot overall KM curve
    km_plot = os.path.join(output_dir, 'km_overall.png')
    _plot_km_curve([kmf_overall], ['Overall'], km_plot, 'Overall Survival')
    results['plot_paths']['km_overall'] = km_plot
    
    # If group column exists, do group comparison
    if group_col in df.columns:
        groups = df[group_col].unique()
        
        if len(groups) == 2:
            # Two-group comparison: KM curves + log-rank test
            kmfs = []
            group_names = []
            
            for g in sorted(groups):
                mask = df[group_col] == g
                kmf = KaplanMeierFitter()
                kmf.fit(
                    df.loc[mask, time_col], 
                    df.loc[mask, event_col], 
                    label=str(g)
                )
                kmfs.append(kmf)
                group_names.append(str(g))
            
            # Log-rank test
            g1, g2 = groups[:2]
            mask1 = df[group_col] == g1
            mask2 = df[group_col] == g2
            
            lr_result = logrank_test(
                df.loc[mask1, time_col],
                df.loc[mask2, time_col],
                df.loc[mask1, event_col],
                df.loc[mask2, event_col]
            )
            
            results['logrank_pvalue'] = lr_result.p_value
            
            # Plot group comparison
            km_group_plot = os.path.join(output_dir, 'km_group_comparison.png')
            _plot_km_curve(
                kmfs, 
                group_names, 
                km_group_plot, 
                f'Survival by {group_col}\nLog-rank p={lr_result.p_value:.4f}'
            )
            results['plot_paths']['km_group'] = km_group_plot
            
            # Cox proportional hazards model
            try:
                cox_df = df[[time_col, event_col, group_col]].copy()
                # Convert group to numeric if needed
                if cox_df[group_col].dtype == 'object':
                    cox_df[group_col] = pd.Categorical(cox_df[group_col]).codes
                
                cph = CoxPHFitter()
                cph.fit(cox_df, duration_col=time_col, event_col=event_col)
                
                cox_summary = os.path.join(output_dir, 'cox_summary.csv')
                cph.summary.to_csv(cox_summary)
                results['cox_hr'] = cph.hazard_ratios_.get(group_col, None)
                results['cox_pvalue'] = cph.summary['p'].get(group_col, None)
                results['cox_summary'] = cox_summary
                
            except Exception as e:
                results['cox_error'] = str(e)
        
        else:
            # Multiple groups: just plot KM curves
            kmfs = []
            group_names = []
            
            for g in sorted(groups):
                mask = df[group_col] == g
                if mask.sum() < 5:  # Skip small groups
                    continue
                kmf = KaplanMeierFitter()
                kmf.fit(
                    df.loc[mask, time_col], 
                    df.loc[mask, event_col], 
                    label=str(g)
                )
                kmfs.append(kmf)
                group_names.append(str(g))
            
            km_multi_plot = os.path.join(output_dir, 'km_multiple_groups.png')
            _plot_km_curve(kmfs, group_names, km_multi_plot, f'Survival by {group_col}')
            results['plot_paths']['km_multi'] = km_multi_plot
    
    # Save summary
    summary_df = pd.DataFrame([{
        'metric': k,
        'value': v if not isinstance(v, dict) else str(v)
    } for k, v in results.items() if k != 'plot_paths'])
    
    summary_csv = os.path.join(output_dir, 'survival_summary.csv')
    summary_df.to_csv(summary_csv, index=False)
    results['summary_csv'] = summary_csv
    
    return results


def _plot_km_curve(kmfitters, labels, output_path, title):
    """Plot Kaplan-Meier survival curves."""
    fig, ax = plt.subplots(figsize=(10, 7))
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(kmfitters)))
    
    for kmf, label, color in zip(kmfitters, labels, colors):
        kmf.plot_survival_function(
            ax=ax,
            color=color,
            linewidth=2,
            label=label,
            ci_show=True,
            ci_alpha=0.2
        )
    
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Survival Probability', fontsize=12)
    ax.set_title(title, fontsize=14)
    if len(kmfitters) > 1:
        ax.legend(loc='lower left', fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def run_gene_survival_analysis(
    input_path: str,
    output_dir: str,
    gene_col: str,
    time_col: str = 'time',
    event_col: str = 'event',
    cutoff: str = 'median'
) -> dict:
    """
    Survival analysis stratified by gene expression level.
    
    Args:
        input_path: Path to data with gene expression and survival info
        output_dir: Directory to save results
        gene_col: Column name of gene to stratify by
        time_col: Column name for survival time
        event_col: Column name for event indicator
        cutoff: 'median' or 'tertile' for stratification
    
    Returns:
        Dictionary with results
    """
    df = read_dataframe(input_path)
    
    if gene_col not in df.columns:
        raise ValueError(f"Gene column '{gene_col}' not found")
    
    # Stratify by expression
    if cutoff == 'median':
        median_expr = df[gene_col].median()
        df['expression_group'] = (df[gene_col] > median_expr).astype(int)
        df['expression_group'] = df['expression_group'].map({0: 'Low', 1: 'High'})
    else:
        tertiles = df[gene_col].quantile([1/3, 2/3])
        df['expression_group'] = pd.cut(
            df[gene_col],
            bins=[-np.inf, tertiles.iloc[0], tertiles.iloc[1], np.inf],
            labels=['Low', 'Medium', 'High']
        )
    
    # Save stratified data
    os.makedirs(output_dir, exist_ok=True)
    stratified_csv = os.path.join(output_dir, f'{gene_col}_stratified.csv')
    df.to_csv(stratified_csv)
    
    # Run standard survival analysis with the new group
    return run_survival_analysis(
        stratified_csv,
        output_dir,
        time_col=time_col,
        event_col=event_col,
        group_col='expression_group'
    )