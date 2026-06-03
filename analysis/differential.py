"""Differential expression analysis module."""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import os

from analysis import read_dataframe

def run_differential_analysis(
    input_path: str,
    output_dir: str,
    group_col: str = 'group',
    control_label: str = 'control',
    treatment_label: str = 'treatment'
) -> dict:
    """
    Run t-test for each gene between two groups.
    
    Args:
        input_path: Path to expression matrix (genes x samples)
        output_dir: Directory to save results
        group_col: Column name indicating group membership
    
    Returns:
        Dictionary with result paths and summary statistics
    """
    # Load data
    df = read_dataframe(input_path)
    
    # Validate columns
    if group_col not in df.columns:
        raise ValueError(f"Group column '{group_col}' not found")
    
    # Separate groups
    control = df[df[group_col] == control_label].drop(columns=[group_col])
    treatment = df[df[group_col] == treatment_label].drop(columns=[group_col])
    
    # Run t-test for each gene
    results = []
    for gene in control.columns:
        t_stat, p_value = stats.ttest_ind(control[gene], treatment[gene])
        log2fc = np.log2(treatment[gene].mean() + 1) - np.log2(control[gene].mean() + 1)
        
        results.append({
            'gene': gene,
            'log2FoldChange': log2fc,
            'pvalue': p_value,
            'negLog10p': -np.log10(p_value + 1e-300)
        })
    
    results_df = pd.DataFrame(results)
    
    # Multiple testing correction (Bonferroni)
    results_df['padj'] = np.minimum(results_df['pvalue'] * len(results_df), 1.0)
    results_df['significant'] = (results_df['padj'] < 0.05) & (abs(results_df['log2FoldChange']) > 1)
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    result_csv = os.path.join(output_dir, 'differential_results.csv')
    results_df.to_csv(result_csv, index=False)
    
    # Generate volcano plot
    plot_path = os.path.join(output_dir, 'volcano_plot.png')
    _generate_volcano_plot(results_df, plot_path)
    
    # Summary
    n_sig = results_df['significant'].sum()
    
    return {
        'result_csv': result_csv,
        'plot_path': plot_path,
        'n_significant': int(n_sig),
        'total_genes': len(results_df)
    }

def _generate_volcano_plot(results_df: pd.DataFrame, output_path: str) -> None:
    """Generate volcano plot for DE results."""
    plt.figure(figsize=(10, 8))
    
    # Color by significance
    colors = ['grey' if not sig else ('red' if fc > 0 else 'blue') 
              for sig, fc in zip(results_df['significant'], results_df['log2FoldChange'])]
    
    plt.scatter(results_df['log2FoldChange'], results_df['negLog10p'], 
                c=colors, alpha=0.6, s=20)
    
    plt.axhline(y=-np.log10(0.05), color='black', linestyle='--', alpha=0.5)
    plt.axvline(x=1, color='black', linestyle='--', alpha=0.5)
    plt.axvline(x=-1, color='black', linestyle='--', alpha=0.5)
    
    plt.xlabel('log2 Fold Change')
    plt.ylabel('-log10 p-value')
    plt.title('Volcano Plot: Differential Expression')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()