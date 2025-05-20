from dataclasses import dataclass
from typing import Tuple, List
import uuid

@dataclass
class Beacon:
    sender_id: uuid.UUID
    mobile: bool  # "mobile" or "fixed"
    position: Tuple[float, float]
    battery: float
    neighbors: List[Tuple[uuid.UUID, str]] # list of known neighbors IDs with a timestamp (last seen)
    timestamp: float  # in simulation time
    range: float