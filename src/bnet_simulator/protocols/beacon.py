from dataclasses import dataclass
from typing import Tuple, List
import uuid

@dataclass
class Beacon:
    sender_id: uuid.UUID # 16 bytes
    mobile: bool # 1 byte
    position: Tuple[float, float] # 8 bytes
    battery: float # 4 bytes
    neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]] # 16 + 4 + 8 bytes per neighbor 
    timestamp: float # 4 bytes

    def size_bytes(self) -> int:
        # Base size + size per neighbor
        # return 16 + 1 + 8 + 4 + (16 + 4 + 8) * len(self.neighbors) + 4
        return 500 # Fixed

    def size_bits(self) -> int:
        return self.size_bytes() * 8