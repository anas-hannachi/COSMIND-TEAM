"""Storage model for PMARS Phase 2 simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StorageModel:
    """Storage capacity and backlog model."""

    total_capacity_mb: float = 2000.0
    free_capacity_mb: float = 2000.0
    queued_storage_mb: float = 0.0
    backlog_size: int = 0
    io_activity: float = 0.0

    def __post_init__(self) -> None:
        if self.total_capacity_mb <= 0:
            raise ValueError("total_capacity_mb must be positive.")
        if self.free_capacity_mb < 0:
            raise ValueError("free_capacity_mb cannot be negative.")
        if self.free_capacity_mb > self.total_capacity_mb:
            raise ValueError("free_capacity_mb cannot exceed total_capacity_mb.")

    def store_data(self, size_mb: float) -> None:
        if size_mb < 0:
            raise ValueError("size_mb cannot be negative.")
        if size_mb > self.free_capacity_mb:
            raise ValueError("storage overflow: not enough free capacity.")
        self.free_capacity_mb -= size_mb
        self.queued_storage_mb += size_mb
        self.backlog_size += 1
        self.io_activity = max(self.io_activity, size_mb)

    def release_data(self, size_mb: float) -> None:
        if size_mb < 0:
            raise ValueError("size_mb cannot be negative.")
        if size_mb > self.queued_storage_mb:
            raise ValueError("cannot release more than queued storage.")
        self.queued_storage_mb -= size_mb
        self.free_capacity_mb += size_mb
        self.backlog_size = max(0, self.backlog_size - 1)

    def apply_to_satellite(self, satellite: "Satellite") -> None:
        """Synchronize storage state into the satellite snapshot fields."""
        from ..core.satellite import Satellite

        if not isinstance(satellite, Satellite):
            raise TypeError("satellite must be a Satellite instance.")
        satellite.storage_free_mb = self.free_capacity_mb
        satellite.queued_storage_mb = self.queued_storage_mb
        satellite.queue_length = self.backlog_size
