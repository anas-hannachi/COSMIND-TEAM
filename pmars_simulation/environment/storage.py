from dataclasses import dataclass

@dataclass(frozen=True)
class StorageModel:
    capacity_mb: float
    def can_store(self, used_mb: float, amount_mb: float) -> bool: return 0 <= amount_mb <= self.capacity_mb - used_mb
