"""Generate test datasets for BioPipe Lite (CSV and TSV formats)."""

import pandas as pd
import numpy as np
import os

np.random.seed(42)


def generate_differential_data(n_samples=20, n_genes=100, output_dir='test_data', fmt='csv'):
    """Generate differential expression test data."""
    os.makedirs(output_dir, exist_ok=True)
    ext = fmt
    sep = '\t' if fmt == 'tsv' else ','
    
    n_control = n_samples // 2
    genes = [f'Gene_{i:03d}' for i in range(n_genes)]
    
    control_data = np.random.normal(5, 1, (n_control, n_genes))
    treatment_data = np.random.normal(5, 1, (n_control, n_genes))
    treatment_data[:, :10] += np.random.normal(3, 0.5, (n_control, 10))
    treatment_data[:, 10:20] -= np.random.normal(3, 0.5, (n_control, 10))
    
    all_data = np.vstack([control_data, treatment_data])
    groups = ['control'] * n_control + ['treatment'] * n_control
    samples = [f'Sample_{i:03d}' for i in range(n_samples)]
    
    df = pd.DataFrame(all_data, index=samples, columns=genes)
    df['group'] = groups
    
    filepath = os.path.join(output_dir, f'differential_test.{ext}')
    df.to_csv(filepath, sep=sep)
    print(f"✓ Differential test data ({fmt.upper()}): {filepath}")
    return filepath


def generate_clustering_data(n_samples=15, n_genes=50, output_dir='test_data', fmt='csv'):
    """Generate clustering test data with 3 inherent clusters."""
    os.makedirs(output_dir, exist_ok=True)
    ext = fmt
    sep = '\t' if fmt == 'tsv' else ','
    
    genes = [f'Gene_{i:03d}' for i in range(n_genes)]
    all_data = []
    samples = []
    
    for i in range(5):
        data = np.random.normal(3, 0.5, n_genes)
        data[:16] += np.random.normal(5, 1, 16)
        all_data.append(data)
        samples.append(f'Cluster1_{i}')
    
    for i in range(5):
        data = np.random.normal(3, 0.5, n_genes)
        data[16:31] += np.random.normal(5, 1, 15)
        all_data.append(data)
        samples.append(f'Cluster2_{i}')
    
    for i in range(5):
        data = np.random.normal(3, 0.5, n_genes)
        data[31:46] += np.random.normal(5, 1, 15)
        all_data.append(data)
        samples.append(f'Cluster3_{i}')
    
    df = pd.DataFrame(np.array(all_data), index=samples, columns=genes)
    
    filepath = os.path.join(output_dir, f'clustering_test.{ext}')
    df.to_csv(filepath, sep=sep)
    print(f"✓ Clustering test data ({fmt.upper()}): {filepath}")
    return filepath


def generate_survival_data(n_patients=50, output_dir='test_data', fmt='csv'):
    """Generate survival analysis test data."""
    os.makedirs(output_dir, exist_ok=True)
    ext = fmt
    sep = '\t' if fmt == 'tsv' else ','
    
    np.random.seed(42)
    patients = [f'Patient_{i:03d}' for i in range(n_patients)]
    
    n_a = n_patients // 2
    groups = ['Low_Risk'] * n_a + ['High_Risk'] * (n_patients - n_a)
    
    times_a = np.random.exponential(500, n_a)
    times_b = np.random.exponential(200, n_patients - n_a)
    
    events_a = np.random.choice([0, 1], n_a, p=[0.2, 0.8])
    events_b = np.random.choice([0, 1], n_patients - n_a, p=[0.2, 0.8])
    
    times = np.concatenate([times_a, times_b])
    events = np.concatenate([events_a, events_b])
    
    gene_expr = np.random.normal(5, 2, (n_patients, 10))
    gene_cols = [f'Gene_{i}' for i in range(10)]
    
    df = pd.DataFrame({
        'patient': patients,
        'time': np.round(times, 1),
        'event': events,
        'group': groups,
    })
    
    for i, col in enumerate(gene_cols):
        df[col] = np.round(gene_expr[:, i], 3)
    
    df.set_index('patient', inplace=True)
    
    filepath = os.path.join(output_dir, f'survival_test.{ext}')
    df.to_csv(filepath, sep=sep)
    print(f"✓ Survival test data ({fmt.upper()}): {filepath}")
    return filepath


if __name__ == '__main__':
    print("=" * 60)
    print("Generating Test Datasets for BioPipe Lite")
    print("=" * 60)
    
    # Generate both CSV and TSV
    for fmt in ['csv', 'tsv']:
        print(f"\n{'='*20} {fmt.upper()} Format {'='*20}")
        generate_differential_data(fmt=fmt)
        generate_clustering_data(fmt=fmt)
        generate_survival_data(fmt=fmt)
    
    print("\n" + "=" * 60)
    print("All test data generated in 'test_data/' directory")
    print("=" * 60)