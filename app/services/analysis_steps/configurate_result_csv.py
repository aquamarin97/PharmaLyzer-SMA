# app\services\analysis_steps\configurate_result_csv.py
# app/services/analysis_steps/configurate_result_csv.py
"""
Final result configuration and CSV preparation.

Adds final columns and prepares DataFrame for export:
- Hasta No (patient number in column-major order)
- Nihai Sonuç (final result from selected analysis mode)
- Proper column ordering

Note: Filename preserves original typo "configurate" for backward compatibility.
"""

from __future__ import annotations

import logging
import string
from typing import Final

import pandas as pd

from app.constants.table_config import CSV_FILE_HEADERS

logger = logging.getLogger(__name__)


# Constants
NUM_ROWS: Final[int] = 8
NUM_COLS: Final[int] = 12
TOTAL_WELLS: Final[int] = 96


class ConfigurateResultCSV:
    """
    Final result configuration step.
    
    Prepares DataFrame for CSV export with:
    - Patient numbering (column-major)
    - Final result selection
    - Column reordering
    """
    
    def __init__(self, checkbox_status: bool):
        self.df: pd.DataFrame | None = None
        self.checkbox_status = checkbox_status
    
    def process(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        """Execute final configuration step."""
        if df is None:
            raise ValueError("DataFrame cannot be None. Called by pipeline.")
        
        if df.empty:
            raise ValueError("No data to process.")
        
        self.df = df.copy(deep=True)
        
        self.add_hasta_no()
        self.add_nihai_sonuc()
        self.sort_by_hasta_no()
        self.reorder_columns()
        
        logger.info("Result configuration completed")
        return self.df
    
    def add_hasta_no(self) -> None:
        """Add patient number column (column-major ordering)."""
        kuyu_no_list = self.generate_kuyu_no(TOTAL_WELLS)
        hasta_no_map = {kuyu: idx + 1 for idx, kuyu in enumerate(kuyu_no_list)}
        self.df["Hasta No"] = self.df["Kuyu No"].map(hasta_no_map)
        logger.debug("Patient numbers added")
    
    def generate_kuyu_no(self, num_rows: int) -> list[str]:
        """Generate well IDs in column-major order."""
        kuyu_no_list: list[str] = []
        letters = string.ascii_uppercase[:NUM_ROWS]  # A-H
        
        for number in range(1, NUM_COLS + 1):  # 1-12
            for letter in letters:  # A-H
                kuyu_no_list.append(f"{letter}{number:02}")
                if len(kuyu_no_list) >= num_rows:
                    return kuyu_no_list
        
        return kuyu_no_list[:num_rows]
    
    def add_nihai_sonuc(self) -> None:
        """Add final result column based on analysis mode."""
        if self.checkbox_status:
            # Reference-free mode
            if "Yazılım Hasta Sonucu" not in self.df.columns:
                raise ValueError("'Yazılım Hasta Sonucu' column not found.")
            self.df["Nihai Sonuç"] = self.df["Yazılım Hasta Sonucu"]
            logger.debug("Final result from reference-free analysis")
        else:
            # Reference-based mode
            if "Referans Hasta Sonucu" not in self.df.columns:
                raise ValueError("'Referans Hasta Sonucu' column not found.")
            self.df["Nihai Sonuç"] = self.df["Referans Hasta Sonucu"]
            logger.debug("Final result from reference-based analysis")
    
    def reorder_columns(self) -> None:
        """Reorder columns according to CSV_FILE_HEADERS."""
        columns_to_include = [col for col in CSV_FILE_HEADERS if col in self.df.columns]
        self.df = self.df[columns_to_include]
        logger.debug(f"Columns reordered: {len(columns_to_include)} columns")
    
    def sort_by_hasta_no(self) -> None:
        """Sort by patient number."""
        if "Hasta No" not in self.df.columns:
            raise ValueError("'Hasta No' column not found.")
        
        self.df = self.df.sort_values(by="Hasta No").reset_index(drop=True)
        logger.debug("Sorted by patient number")


__all__ = ["ConfigurateResultCSV"]