"""Abstract base class for all telemetry readers."""

from abc import ABC, abstractmethod


class TelemetryReader(ABC):
    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def is_connected(self):
        pass
