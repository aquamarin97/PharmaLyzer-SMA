# app\services\analysis_summary.py
# app/services/analysis_summary.py
"""
Analysis summary data structure.

Immutable dataclass containing statistical summary of PCR analysis results.
All fields are pre-formatted strings ready for display.

Usage:
    from app.services.analysis_summary import AnalysisSummary
    
    summary = AnalysisSummary(
        analyzed_well_count=": 96",
        healthy_count=": 85",
        carrier_count=": 8",
        healthy_avg=": 1.025",
        std=": 0.042",
        cv=": 4.10"
    )

Note:
    All values include leading ": " for consistent display formatting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisSummary:
    """
    Immutable PCR analysis statistical summary.
    
    All fields are pre-formatted strings with leading ": " for display.
    Empty string ("") indicates unavailable/not calculated.
    
    Attributes:
        analyzed_well_count: Total wells excluding empty wells
        safezone_count: Wells in regression safe zone
        riskyarea_count: Wells in regression risky area
        healthy_count: Wells classified as healthy
        carrier_count: Wells classified as carrier
        uncertain_count: Wells classified as uncertain
        healthy_avg: Mean ratio for healthy samples (safe zone, 0.7-1.3 range)
        std: Standard deviation of healthy ratios
        cv: Coefficient of variation (%) = (std / mean) * 100
    
    Example:
        >>> summary = AnalysisSummary(
        ...     analyzed_well_count=": 96",
        ...     healthy_count=": 85",
        ...     healthy_avg=": 1.025",
        ...     std=": 0.042",
        ...     cv=": 4.10"
        ... )
        >>> print(summary.healthy_avg)
        : 1.025
    """
    
    analyzed_well_count: str = ""
    """Total analyzed wells (excluding empty wells)"""
    
    safezone_count: str = ""
    """Wells in regression safe zone"""
    
    riskyarea_count: str = ""
    """Wells in regression risky area"""
    
    healthy_count: str = ""
    """Wells classified as healthy"""
    
    carrier_count: str = ""
    """Wells classified as carrier"""
    
    uncertain_count: str = ""
    """Wells classified as uncertain"""
    
    healthy_avg: str = ""
    """Mean statistical ratio for healthy samples in safe zone (0.7-1.3)"""
    
    std: str = ""
    """Standard deviation of healthy ratios"""
    
    cv: str = ""
    """Coefficient of variation (%) = (std / mean) * 100"""


__all__ = ["AnalysisSummary"]