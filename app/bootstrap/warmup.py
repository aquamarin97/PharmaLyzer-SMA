# app\bootstrap\warmup.py
# app/bootstrap/warmup.py
"""
Application startup warmup routine.

This module handles first-call overhead for heavy scientific libraries
by pre-importing and performing initial operations during splash screen
display. This improves perceived performance when users first interact
with analysis features.

What gets warmed up:
    - NumPy: Import + first matrix operation (JIT compilation)
    - scikit-learn: LinearRegression + KMeans first fit
    - SciPy: optimize.minimize first call
    - Matplotlib: First figure creation
    - PyQtGraph: Configuration and import

Why warmup matters:
    - First NumPy operation: ~200ms (JIT compilation)
    - First sklearn fit: ~300ms (lazy initialization)
    - First matplotlib figure: ~500ms (backend initialization)
    - Total saved: ~1+ second on first user action

Usage:
    from app.bootstrap.warmup import run_warmup, WarmupConfig
    from app.bootstrap.splash import update_splash_progress
    
    def progress_callback(message: str, percent: int):
        update_splash_progress(splash, message, percent)
    
    # Run warmup with progress updates
    run_warmup(progress_callback)
    
    # Custom configuration
    config = WarmupConfig(numpy_size=500, kmeans_clusters=10)
    run_warmup(progress_callback, config)

Design:
    - Progress: 0% to 100% in ~8 steps
    - UI messages: User-friendly from i18n ("Loading modules...")
    - Log messages: Technical detail for debugging
    - Error handling: Continues on import failures (logs warnings)

Note:
    Warmup is optional - controlled by AppSettings.warmup_enabled flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Final

from app.i18n import t_list

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE ALIASES
# ============================================================================

ProgressCallback = Callable[[str, int], None]
"""
Progress callback signature.

Args:
    message: Progress message to display (localized)
    percent: Progress percentage (0-100)
"""


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass(frozen=True, slots=True)
class WarmupConfig:
    """
    Warmup routine configuration.
    
    Controls the intensity and parameters of warmup operations.
    Higher values = longer warmup but more thorough cache warming.
    
    Attributes:
        numpy_size: Matrix size for NumPy warmup (size x size)
        kmeans_clusters: Number of clusters for KMeans warmup
        random_state: Random seed for reproducibility
        scipy_maxiter: Maximum iterations for scipy.optimize
    """
    
    numpy_size: int = 200
    """NumPy matrix size (200x200 = 40K elements, ~50ms)"""
    
    kmeans_clusters: int = 5
    """KMeans cluster count (5 clusters, ~100ms)"""
    
    random_state: int = 42
    """Random seed for reproducible warmup behavior"""
    
    scipy_maxiter: int = 20
    """scipy.optimize.minimize max iterations"""


# Default configuration (balanced performance)
DEFAULT_WARMUP_CONFIG: Final[WarmupConfig] = WarmupConfig()


# ============================================================================
# PROGRESS MANAGEMENT
# ============================================================================

class WarmupStep:
    """
    Warmup step definition.
    
    Tracks progress percentage and logging detail for each warmup step.
    """
    
    def __init__(
        self,
        step_index: int,
        percent: int,
        log_detail: str
    ):
        self.step_index = step_index
        self.percent = percent
        self.log_detail = log_detail


# Warmup progress plan (smooth 0-100% distribution)
_WARMUP_STEPS: Final[list[WarmupStep]] = [
    WarmupStep(0, 5, "warmup start"),
    WarmupStep(0, 10, "numpy import + first operation"),
    WarmupStep(1, 15, "qt boundary (main thread checkpoint)"),
    WarmupStep(2, 25, "sklearn import"),
    WarmupStep(2, 35, "sklearn first fit (LR + KMeans)"),
    WarmupStep(3, 45, "scipy import"),
    WarmupStep(3, 55, "scipy.optimize.minimize first call"),
    WarmupStep(4, 70, "matplotlib import"),
    WarmupStep(4, 80, "matplotlib first figure"),
    WarmupStep(5, 90, "pyqtgraph import + config"),
    WarmupStep(6, 95, "finalizing warmup"),
    WarmupStep(7, 100, "warmup complete"),
]


def _get_safe_messages() -> list[str]:
    """
    Get localized loading messages with fallback.
    
    Returns:
        List of loading messages from i18n, or default if unavailable
    """
    messages = t_list("loading.messages")
    return messages if messages else ["Loading..."]


def _compose_ui_message(step_index: int, percent: int) -> str:
    """
    Compose user-friendly progress message.
    
    Args:
        step_index: Current step index (0-7)
        percent: Progress percentage (0-100)
    
    Returns:
        Formatted message like "Loading modules...  25%"
    """
    messages = _get_safe_messages()
    
    # Get message for step (use last if out of range)
    message_index = min(step_index, len(messages) - 1)
    base_message = messages[message_index]
    
    return f"{base_message}  {percent}%"


def _report_progress(
    progress_callback: ProgressCallback | None,
    step: WarmupStep
) -> None:
    """
    Report warmup progress via callback and logging.
    
    Args:
        progress_callback: Optional callback to update UI
        step: WarmupStep with progress information
    """
    # Update UI if callback provided
    if progress_callback is not None:
        try:
            ui_message = _compose_ui_message(step.step_index, step.percent)
            progress_callback(ui_message, step.percent)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")
    
    # Always log technical detail
    logger.info(f"[Warmup] {step.log_detail} ({step.percent}%)")


# ============================================================================
# WARMUP OPERATIONS
# ============================================================================

class WarmupError(Exception):
    """Raised when warmup encounters critical error."""
    pass


def run_warmup(
    progress_callback: ProgressCallback | None = None,
    config: WarmupConfig | None = None
) -> None:
    """
    Run application warmup routine.
    
    Performs first-call operations on heavy libraries to reduce latency
    when users first interact with analysis features. Shows smooth
    progress from 0% to 100%.
    
    Args:
        progress_callback: Optional callback for UI progress updates
                          Signature: (message: str, percent: int) -> None
        config: Optional warmup configuration (uses defaults if None)
    
    Example:
        >>> from app.bootstrap.warmup import run_warmup
        >>> 
        >>> def update_ui(msg: str, pct: int):
        ...     splash.showMessage(f"{msg}  {pct}%")
        >>> 
        >>> run_warmup(progress_callback=update_ui)
    
    Error Handling:
        - Import failures are logged as warnings (non-fatal)
        - Critical errors raise WarmupError
        - Warmup continues on non-critical errors
    
    Note:
        UI messages are localized and user-friendly.
        Log messages contain technical details for debugging.
    """
    if config is None:
        config = DEFAULT_WARMUP_CONFIG
    
    logger.info("=" * 60)
    logger.info("Starting warmup routine")
    logger.info(f"Config: numpy_size={config.numpy_size}, "
                f"kmeans_clusters={config.kmeans_clusters}")
    logger.info("=" * 60)
    
    try:
        _run_warmup_steps(progress_callback, config)
        logger.info("Warmup completed successfully")
        
    except Exception as e:
        logger.error(f"Warmup failed: {e}", exc_info=True)
        raise WarmupError(f"Critical warmup error: {e}") from e


def _run_warmup_steps(
    progress_callback: ProgressCallback | None,
    config: WarmupConfig
) -> None:
    """
    Execute warmup steps sequentially.
    
    Args:
        progress_callback: Optional progress callback
        config: Warmup configuration
    """
    step_iter = iter(_WARMUP_STEPS)
    
    # Step 0-1: Start + NumPy
    _report_progress(progress_callback, next(step_iter))  # 5%
    _report_progress(progress_callback, next(step_iter))  # 10%
    _warmup_numpy(config)
    
    # Step 2: Qt boundary
    _report_progress(progress_callback, next(step_iter))  # 15%
    
    # Step 3-4: scikit-learn
    _report_progress(progress_callback, next(step_iter))  # 25%
    _report_progress(progress_callback, next(step_iter))  # 35%
    _warmup_sklearn(config)
    
    # Step 5-6: SciPy
    _report_progress(progress_callback, next(step_iter))  # 45%
    _report_progress(progress_callback, next(step_iter))  # 55%
    _warmup_scipy(config)
    
    # Step 7-8: Matplotlib
    _report_progress(progress_callback, next(step_iter))  # 70%
    _report_progress(progress_callback, next(step_iter))  # 80%
    _warmup_matplotlib()
    
    # Step 9: PyQtGraph
    _report_progress(progress_callback, next(step_iter))  # 90%
    _warmup_pyqtgraph()
    
    # Step 10-11: Finalize
    _report_progress(progress_callback, next(step_iter))  # 95%
    _report_progress(progress_callback, next(step_iter))  # 100%


def _warmup_numpy(config: WarmupConfig) -> None:
    """
    Warm up NumPy with matrix multiplication.
    
    Args:
        config: Warmup configuration
    """
    try:
        import numpy as np
        
        # Create random matrix and perform multiplication
        # This triggers NumPy's JIT compilation and memory allocation
        size = config.numpy_size
        matrix = np.random.rand(size, size)
        _ = matrix @ matrix  # Matrix multiplication
        
        logger.debug(f"NumPy warmed up: {size}x{size} matrix multiplication")
        
    except ImportError as e:
        logger.warning(f"NumPy import failed: {e}")


def _warmup_sklearn(config: WarmupConfig) -> None:
    """
    Warm up scikit-learn with LinearRegression and KMeans.
    
    Args:
        config: Warmup configuration
    """
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
        from sklearn.cluster import KMeans
        
        # Linear regression warmup
        X = np.array([[0.0], [1.0]])
        y = np.array([0.0, 1.0])
        LinearRegression().fit(X, y)
        
        # KMeans warmup
        X_kmeans = np.random.rand(config.numpy_size, 1)
        KMeans(
            n_clusters=config.kmeans_clusters,
            random_state=config.random_state
        ).fit(X_kmeans)
        
        logger.debug(
            f"scikit-learn warmed up: LinearRegression + "
            f"KMeans(k={config.kmeans_clusters})"
        )
        
    except ImportError as e:
        logger.warning(f"scikit-learn import failed: {e}")


def _warmup_scipy(config: WarmupConfig) -> None:
    """
    Warm up SciPy with optimize.minimize.
    
    Args:
        config: Warmup configuration
    """
    try:
        import numpy as np
        from scipy.optimize import minimize
        
        # Simple quadratic optimization
        def objective(x):
            return float((x[0] - 0.1234) ** 2)
        
        minimize(
            objective,
            x0=np.array([0.0]),
            bounds=[(-4.0, 4.0)],
            method="L-BFGS-B",
            options={"maxiter": config.scipy_maxiter},
        )
        
        logger.debug(
            f"SciPy warmed up: optimize.minimize "
            f"(maxiter={config.scipy_maxiter})"
        )
        
    except ImportError as e:
        logger.warning(f"SciPy import failed: {e}")


def _warmup_matplotlib() -> None:
    """Warm up Matplotlib with first figure creation."""
    try:
        import matplotlib.pyplot as plt
        
        # Create and immediately close figure
        # This initializes the matplotlib backend
        fig = plt.figure()
        plt.close(fig)
        
        logger.debug("Matplotlib warmed up: first figure created")
        
    except ImportError as e:
        logger.warning(f"Matplotlib import failed: {e}")


def _warmup_pyqtgraph() -> None:
    """Warm up PyQtGraph with configuration."""
    try:
        import pyqtgraph as pg
        
        # Set global configuration options
        pg.setConfigOptions(antialias=True)
        
        logger.debug("PyQtGraph warmed up: antialiasing enabled")
        
    except ImportError as e:
        logger.warning(f"PyQtGraph import failed: {e}")


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main API
    "run_warmup",
    
    # Configuration
    "WarmupConfig",
    "DEFAULT_WARMUP_CONFIG",
    
    # Type aliases
    "ProgressCallback",
    
    # Exceptions
    "WarmupError",
]