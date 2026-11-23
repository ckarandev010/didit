"""didit: check an AI coding agent's "done" summary against what its tools actually did."""
from .check import check_turn
from .claims import extract
from .transcript import load

__version__ = "0.1.0"
__all__ = ["check_turn", "extract", "load", "__version__"]
