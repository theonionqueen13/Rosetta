import pandas as pd
import numpy as np
from rosetta.calc import calculate_chart


def test_calculate_chart():
    df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
    test_csv = "tests/expected_chart_output.csv"
    expected_df = pd.read_csv(test_csv)

    # Reset index to ensure alignment
    df_reset = df.reset_index(drop=True)
    expected_reset = expected_df.reset_index(drop=True)

    # Normalize null values (convert both pd.NA and empty strings to np.nan)
    df_reset = df_reset.fillna(np.nan).replace('', np.nan)
    expected_reset = expected_reset.fillna(np.nan).replace('', np.nan)

    # Convert dict columns to strings for comparison (CSV stores dicts as strings)
    df_reset['Dignity'] = df_reset['Dignity'].astype(str)

    # Assert that the diff is null (DataFrames are equal)
    pd.testing.assert_frame_equal(df_reset, expected_reset, check_dtype=False)
