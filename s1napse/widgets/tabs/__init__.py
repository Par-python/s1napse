"""Per-tab UI modules. Each file owns one tab's layout + per-tick update."""

# Each tab module exports a class with the signature:
#     class XxxTab(QWidget):
#         def __init__(self, app: 'TelemetryApp', parent=None) -> None: ...
#         def update_tick(self, data: dict | None) -> None: ...
#
# The `app` reference gives the tab access to engines and shared state. Long-term
# we'll replace this with explicit signals; for v1 the direct ref keeps the
# refactor minimal.

from .race import RaceTab
from .tyres import TyresTab
from .dashboard import DashboardTab

__all__ = ['RaceTab', 'TyresTab', 'DashboardTab']
