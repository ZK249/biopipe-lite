"""Analysis modules package."""

import os
import pandas as pd


def read_dataframe(filepath: str, index_col=0, **kwargs) -> pd.DataFrame:
    """Read a dataframe from CSV or TSV file based on extension.

    Args:
        filepath: Path to the data file.
        index_col: Column to use as row labels (passed to read_csv).
        **kwargs: Additional arguments passed to pandas.read_csv.

    Returns:
        Parsed DataFrame.
    """
    ext = os.path.splitext(filepath)[1].lower()
    sep = '\t' if ext in ('.tsv', '.txt') else ','
    return pd.read_csv(filepath, sep=sep, index_col=index_col, **kwargs)
