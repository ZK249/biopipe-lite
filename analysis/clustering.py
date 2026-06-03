"""Clustering analysis module."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.spatial.distance import pdist
import os

from analysis import read_dataframe


def run_clustering_analysis(
    input_path: str,
    output_dir: str,
    n_clusters: int = 3,
    method: str = 'kmeans'
) -> dict:
    """
    Run clustering analysis on expression matrix.
    
    Args:
        input_path: Path to expression matrix (genes x samples)
        output_dir: Directory to save results
        n_clusters: Number of clusters
        method: 'kmeans' or 'hierarchical'
    
    Returns:
        Dictionary with result paths and summary
    """
    # Load data
    df = read_dataframe(input_path)
    
    # Assume rows are genes, columns are samples
    # Transpose so rows are samples for clustering
    expr = df.T
    
    # Remove any non-numeric columns (like group labels)
    numeric_cols = expr.select_dtypes(include=[np.number]).columns
    expr_numeric = expr[numeric_cols]
    
    # Standardize features (genes)
    scaler = StandardScaler()
    expr_scaled = scaler.fit_transform(expr_numeric)
    
    # Run clustering
    if method == 'kmeans':
        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = clusterer.fit_predict(expr_scaled)
    else:
        # Hierarchical clustering
        clusterer = AgglomerativeClustering(n_clusters=n_clusters)
        labels = clusterer.fit_predict(expr_scaled)
    
    # Add labels to original data
    expr['cluster'] = labels
    
    # PCA for visualization
    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(expr_scaled)
    
    # Save cluster assignments
    os.makedirs(output_dir, exist_ok=True)
    cluster_csv = os.path.join(output_dir, 'cluster_assignments.csv')
    expr[['cluster']].to_csv(cluster_csv)
    
    # Generate plots
    plot_paths = {}
    
    # PCA scatter plot colored by cluster
    pca_plot = os.path.join(output_dir, 'pca_clusters.png')
    _plot_pca_clusters(pca_result, labels, n_clusters, pca_plot)
    plot_paths['pca'] = pca_plot
    
    # Heatmap of top variable genes
    heatmap_plot = os.path.join(output_dir, 'heatmap.png')
    _plot_heatmap(expr_numeric, labels, heatmap_plot)
    plot_paths['heatmap'] = heatmap_plot
    
    # Hierarchical dendrogram (if applicable)
    if method == 'hierarchical':
        dendro_plot = os.path.join(output_dir, 'dendrogram.png')
        _plot_dendrogram(expr_scaled, labels, dendro_plot)
        plot_paths['dendrogram'] = dendro_plot
    
    # Cluster summary
    cluster_sizes = pd.Series(labels).value_counts().sort_index().to_dict()
    
    return {
        'result_csv': cluster_csv,
        'plot_paths': plot_paths,
        'n_clusters': n_clusters,
        'cluster_sizes': cluster_sizes,
        'pca_variance_ratio': pca.explained_variance_ratio_.tolist(),
        'method': method
    }


def _plot_pca_clusters(pca_result, labels, n_clusters, output_path):
    """Plot PCA scatter with cluster colors."""
    plt.figure(figsize=(10, 8))
    
    colors = plt.cm.tab10(np.linspace(0, 1, n_clusters))
    
    for i in range(n_clusters):
        mask = labels == i
        plt.scatter(
            pca_result[mask, 0], 
            pca_result[mask, 1],
            c=[colors[i]], 
            label=f'Cluster {i}',
            alpha=0.7,
            s=100
        )
    
    plt.xlabel(f'PC1')
    plt.ylabel(f'PC2')
    plt.title('PCA: Sample Clusters')
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _plot_heatmap(expr_numeric, labels, output_path):
    """Plot heatmap of top variable genes by cluster."""
    # Select top 50 most variable genes
    gene_vars = expr_numeric.var(axis=0)
    top_genes = gene_vars.nlargest(50).index
    
    # Subset and sort by cluster
    plot_df = expr_numeric[top_genes].copy()
    plot_df['cluster'] = labels
    plot_df = plot_df.sort_values('cluster')
    cluster_labels = plot_df['cluster'].values
    plot_df = plot_df.drop('cluster', axis=1)
    
    # Standardize for visualization
    plot_scaled = StandardScaler().fit_transform(plot_df.T).T
    
    plt.figure(figsize=(12, 10))
    
    # Create color bar for clusters
    cluster_colors = plt.cm.tab10(cluster_labels / cluster_labels.max())
    
    g = sns.clustermap(
        plot_scaled,
        row_cluster=False,
        col_cluster=True,
        cmap='RdBu_r',
        center=0,
        figsize=(12, 10),
        row_colors=cluster_colors
    )
    
    g.savefig(output_path, dpi=150)
    plt.close('all')


def _plot_dendrogram(expr_scaled, labels, output_path):
    """Plot hierarchical dendrogram."""
    plt.figure(figsize=(14, 6))
    
    linked = linkage(expr_scaled, method='ward')
    
    dendrogram(
        linked,
        truncate_mode='lastp',
        p=30,
        leaf_rotation=90,
        leaf_font_size=10,
        show_contracted=True
    )
    
    plt.title('Hierarchical Clustering Dendrogram')
    plt.xlabel('Sample Index or (Cluster Size)')
    plt.ylabel('Distance')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()