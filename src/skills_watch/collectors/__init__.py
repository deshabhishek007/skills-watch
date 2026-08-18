from .base import Collector, get_collector, COLLECTORS
from . import greenhouse, workday, workable, bamboohr, lever, automattic, generic  # noqa: F401 (registers collectors)

__all__ = ["Collector", "get_collector", "COLLECTORS"]
