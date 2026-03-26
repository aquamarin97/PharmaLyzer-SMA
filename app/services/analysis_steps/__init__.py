# app\services\analysis_steps\__init__.py
# app/services/analysis_steps/__init__.py
"""
Analysis pipeline steps.

Sequential steps for PCR data analysis:
1. CSVProcessor - Data preprocessing
2. CalculateRegression - Outlier detection
3. CalculateWithReferance - Reference-based calculation
4. CalculateWithoutReference - Reference-free calculation
5. ConfigurateResultCSV - Final result preparation

Critical:
    These steps contain calibrated algorithms.
    Calculation logic should not be modified without validation.
"""

from .calculate_regression import CalculateRegression
from .calculate_with_referance import CalculateWithReferance
from .calculate_without_reference import CalculateWithoutReference, ClusterInfo
from .configurate_result_csv import ConfigurateResultCSV
from .csv_processor import CSVProcessor

__all__ = [
    "CSVProcessor",
    "CalculateRegression",
    "CalculateWithReferance",
    "CalculateWithoutReference",
    "ConfigurateResultCSV",
    "ClusterInfo",
]