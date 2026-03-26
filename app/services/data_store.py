# app/services/data_store.py
"""
Thread-safe DataFrame storage and access service.

This module provides a centralized, thread-safe store for PCR analysis data
using the singleton pattern. All read/write operations are protected by RLock.

Thread Safety:
    This module is completely thread-safe. Can be safely used from multiple
    threads simultaneously.

Typical Usage:
    # Store data
    df = pd.DataFrame({'col': [1, 2, 3]})
    DataStore.set_df(df, copy=True)
    
    # Read data (reference)
    current = DataStore.get_df()
    
    # Read data (safe copy)
    df_copy = DataStore.get_df_copy()
    
    # Clear
    DataStore.clear()

Warning:
    DataFrames obtained via get_df() are REFERENCES. Modifications affect
    the original data. For safe operations, use get_df_copy().

Note:
    This module uses singleton pattern. Do not instantiate - call class
    methods directly.
"""

from __future__ import annotations

import logging
import threading

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# DATASTORE
# ============================================================================

class DataStore:
    """
    Thread-safe DataFrame storage and access class.
    
    This class stores PCR analysis data centrally and provides thread-safe
    access. Uses singleton pattern - single DataFrame instance shared across
    the entire application.
    
    Class Attributes:
        _lock: Reentrant lock for thread-safe operations
        _df: Stored DataFrame instance
    
    Thread Safety:
        All public methods are thread-safe. Protected by RLock for
        concurrent access.
    
    Performance Notes:
        - set_df() stores reference by default (O(1))
        - set_df(copy=True) performs deep copy (O(n))
        - get_df() returns reference (O(1))
        - get_df_copy() performs deep copy each call (O(n))
    
    Example:
        >>> # Thread 1
        >>> df = pd.DataFrame({'A': [1, 2, 3]})
        >>> DataStore.set_df(df, copy=True)
        >>> 
        >>> # Thread 2
        >>> current = DataStore.get_df_copy()
        >>> print(current['A'].sum())  # 6
        >>> 
        >>> # Thread 3
        >>> DataStore.clear()
    """
    
    # ---- Class Attributes (Private) ----
    
    _lock: threading.RLock = threading.RLock()
    """Reentrant lock for thread-safe operations."""
    
    _df: pd.DataFrame | None = None
    """Stored DataFrame. None if store is empty."""
    
    _version: int = 0  # ← EKLE: her set_df/clear'da artar

    # ---- Public Class Methods ----
    @classmethod
    def get_version(cls) -> int:
        """
        Mevcut store versiyonunu döner.
        
        Her set_df() ve clear() çağrısında artar.
        Cache invalidation için kullanılır.
        
        Returns:
            int: Mevcut versiyon numarası
        """
        with cls._lock:
            return cls._version
        
    @classmethod
    def set_df(cls, df: pd.DataFrame, *, copy: bool = False) -> None:
        """
        Store DataFrame in the store.
        
        Saves the provided DataFrame to the store. By default stores
        reference (for performance), but can perform deep copy with copy=True.
        
        Args:
            df: DataFrame to store. Cannot be None.
            copy: If True, performs deep copy; if False, stores reference.
                  Default: False (for performance)
        
        Raises:
            ValueError: If df is None
            TypeError: If df is not a pandas DataFrame
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Performance:
            - copy=False: O(1) - reference assignment only
            - copy=True: O(n*m) - deep copy for n rows, m columns
        
        Example:
            >>> df = pd.DataFrame({'col': [1, 2, 3]})
            >>> 
            >>> # Store reference (fast)
            >>> DataStore.set_df(df)
            >>> 
            >>> # Store deep copy (safe)
            >>> DataStore.set_df(df, copy=True)
        
        Warning:
            When copy=False, external code modifying the DataFrame
            will affect stored data. For production code, copy=True
            is recommended.
        """
        if df is None:
            raise ValueError("DataFrame cannot be None. Use clear() to reset store.")
        
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"Expected pandas DataFrame, got {type(df).__name__}"
            )
        
        with cls._lock:
            cls._df = df.copy(deep=True) if copy else df
            cls._version += 1  # ← EKLE
            logger.debug(
                f"DataFrame set in store: shape={df.shape}, "
                f"copy={copy}, version={cls._version}"
            )

    @classmethod
    def get_df(cls) -> pd.DataFrame | None:
        """
        Get DataFrame from store (reference).
        
        Returns the REFERENCE to the stored DataFrame. Modifications to
        the returned DataFrame will affect the store.
        
        Returns:
            Stored DataFrame or None (if store is empty)
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Performance:
            O(1) - Only reference is returned, no copying
        
        Example:
            >>> DataStore.set_df(pd.DataFrame({'A': [1, 2, 3]}))
            >>> df = DataStore.get_df()
            >>> 
            >>> # WARNING: This modification affects the store!
            >>> df['A'] = df['A'] * 2
        
        Warning:
            Returned DataFrame is a REFERENCE! Modifications affect the store.
            For safe operations, use get_df_copy().
        
        See Also:
            get_df_copy(): Returns safe, copied DataFrame
        """
        with cls._lock:
            if cls._df is None:
                logger.debug("get_df() called but store is empty")
            return cls._df
    
    @classmethod
    def get_df_copy(cls) -> pd.DataFrame | None:
        """
        Get deep copy of DataFrame from store.
        
        Returns a deep copy of the stored DataFrame. Modifications to
        the returned DataFrame will NOT affect the store.
        
        Returns:
            Deep copy of stored DataFrame or None (if store is empty)
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Performance:
            O(n*m) - Deep copy performed on each call (n rows, m columns)
            Can be expensive for frequent calls on large DataFrames.
        
        Example:
            >>> DataStore.set_df(pd.DataFrame({'A': [1, 2, 3]}))
            >>> df_copy = DataStore.get_df_copy()
            >>> 
            >>> # This modification does NOT affect the store
            >>> df_copy['A'] = df_copy['A'] * 2
            >>> 
            >>> # Store still has original values
            >>> print(DataStore.get_df()['A'].tolist())  # [1, 2, 3]
        
        Note:
            For large DataFrames, get_df_copy() is expensive.
            If only reading, use get_df().
        
        See Also:
            get_df(): Returns reference (performant but risky)
        """
        with cls._lock:
            if cls._df is None:
                logger.debug("get_df_copy() called but store is empty")
                return None
            
            return cls._df.copy(deep=True)
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear DataFrame from store.
        
        Empties the store and sets _df to None. Garbage collector must
        run for memory to be freed.
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Performance:
            O(1) - Only reference set to None
        
        Example:
            >>> DataStore.set_df(pd.DataFrame({'A': [1, 2, 3]}))
            >>> print(DataStore.has_df())  # True
            >>> 
            >>> DataStore.clear()
            >>> print(DataStore.has_df())  # False
        
        Note:
            After clear(), get_df() and get_df_copy() return None.
        
        See Also:
            has_df(): Checks if store is empty
        """
        with cls._lock:
            if cls._df is not None:
                logger.debug(f"Clearing DataFrame from store: shape={cls._df.shape}")
            cls._df = None
            cls._version += 1  
    
    @classmethod
    def has_df(cls) -> bool:
        """
        Check if store contains DataFrame.
        
        Returns:
            True: Store contains DataFrame
            False: Store is empty
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Performance:
            O(1) - None check only
        
        Example:
            >>> DataStore.clear()
            >>> print(DataStore.has_df())  # False
            >>> 
            >>> DataStore.set_df(pd.DataFrame({'A': [1]}))
            >>> print(DataStore.has_df())  # True
        
        Note:
            This method does not check DataFrame contents,
            only whether it's None.
        """
        with cls._lock:
            return cls._df is not None
    
    @classmethod
    def get_info(cls) -> dict[str, object]:
        """
        Get store information (for debugging).
        
        Returns:
            Dictionary containing store status:
                - 'has_data': Does store have DataFrame? (bool)
                - 'shape': DataFrame shape or None
                - 'columns': Column names or None
                - 'memory_mb': Approximate memory usage (MB) or None
        
        Thread Safety:
            This method is thread-safe. Protected by RLock.
        
        Example:
            >>> DataStore.set_df(pd.DataFrame({'A': [1, 2, 3]}))
            >>> info = DataStore.get_info()
            >>> print(info)
            {
                'has_data': True,
                'shape': (3, 1),
                'columns': ['A'],
                'memory_mb': 0.001
            }
        
        Note:
            This method is for debugging and monitoring.
            Don't use in performance-critical production code.
        """
        with cls._lock:
            if cls._df is None:
                return {
                    'has_data': False,
                    'shape': None,
                    'columns': None,
                    'memory_mb': None,
                }
            
            # Calculate memory usage (in MB)
            memory_bytes = cls._df.memory_usage(deep=True).sum()
            memory_mb = float(memory_bytes) / (1024 * 1024)
            
            return {
                'has_data': True,
                'shape': cls._df.shape,
                'columns': cls._df.columns.tolist(),
                'memory_mb': round(memory_mb, 3),
            }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def store_dataframe(df: pd.DataFrame, *, safe: bool = True) -> None:
    """
    Convenience function to store DataFrame.
    
    Args:
        df: DataFrame to store
        safe: If True, performs deep copy (default)
    
    Example:
        >>> df = pd.DataFrame({'A': [1, 2, 3]})
        >>> store_dataframe(df, safe=True)
    
    Note:
        This function wraps DataStore.set_df().
    """
    DataStore.set_df(df, copy=safe)


def retrieve_dataframe(*, safe: bool = True) -> pd.DataFrame | None:
    """
    Convenience function to retrieve DataFrame.
    
    Args:
        safe: If True, returns deep copy (default)
    
    Returns:
        DataFrame or None
    
    Example:
        >>> df = retrieve_dataframe(safe=True)
        >>> if df is not None:
        ...     print(df.shape)
    
    Note:
        This function wraps DataStore.get_df_copy() or get_df().
    """
    return DataStore.get_df_copy() if safe else DataStore.get_df()


def is_store_empty() -> bool:
    """
    Check if store is empty.
    
    Returns:
        True if store is empty
    
    Example:
        >>> if is_store_empty():
        ...     print("Store empty, load data")
    
    Note:
        This function wraps DataStore.has_df().
    """
    return not DataStore.has_df()


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main class
    "DataStore",
    
    # Convenience functions
    "store_dataframe",
    "retrieve_dataframe",
    "is_store_empty",
]