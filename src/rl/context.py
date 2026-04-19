"""
State/Context representation for the RL agent.
Defines the observation space and how state is extracted from buoy environment.
"""

from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
import math


@dataclass
class ContextVector:
    """
    Contextual state vector for the multi-armed bandit.
    
    Features extracted from buoy environment:
    - neighbors_count: Number of 1-hop neighbors
    - time_since_novelty: Seconds since new node was discovered (novelty indicator)
    - congestion_level: Estimated channel congestion (0.0-1.0)
    - battery_percent: Battery level as percentage (0.0-1.0)
    - velocity_magnitude: Speed of movement (0.0 normalized to default_velocity)
    - reception_rate_trend: Recent beacon reception trend (0.0-1.0)
    """
    neighbors_count: float           # [0, 60] → normalized to [0, 1]
    time_since_novelty: float        # [0, inf] seconds → sigmoid
    congestion_level: float          # [0, 1] from channel busy metrics
    battery_percent: float           # [0, 1]
    velocity_magnitude: float        # [0, 1] (speed / default_velocity)
    reception_rate_trend: float      # [0, 1] beacons received in window
    
    def to_array(self) -> Tuple[float, ...]:
        """Convert context to tuple for feeding to agent."""
        return (
            self.neighbors_count,
            self.time_since_novelty,
            self.congestion_level,
            self.battery_percent,
            self.velocity_magnitude,
            self.reception_rate_trend,
        )
    
    @staticmethod
    def from_buoy_state(
        buoy,
        default_velocity: float = 15.0,
        max_neighbors: int = 60,
        beacon_window_size: int = 10,
    ) -> "ContextVector":
        """
        Extract context vector from current buoy state.
        
        Args:
            buoy: Buoy instance with current state
            default_velocity: Normalization factor for speed
            max_neighbors: Maximum expected neighbors (for normalization)
            beacon_window_size: Time window (seconds) for reception rate calculation
        
        Returns:
            ContextVector with normalized features [0, 1]
        """
        # Feature 1: Neighbors count (normalized)
        neighbors_count = min(len(buoy.neighbors) / max_neighbors, 1.0)
        
        # Feature 2: Time since last novelty (new neighbor discovered)
        # If no discovered_nodes, use a large time value
        current_time = buoy.simulator.current_time if hasattr(buoy, 'simulator') else 0
        if hasattr(buoy, 'discovered_nodes') and buoy.discovered_nodes:
            # Get timestamp of last discovered node (tuple: (UUID, timestamp, position))
            last_discovery_time = max(node[1] for node in buoy.discovered_nodes)
            time_since_novelty = current_time - last_discovery_time
        else:
            time_since_novelty = float('inf')
        
        # Sigmoid to map [0, inf] to [0, 1], with inflection at 30 seconds
        time_since_novelty_norm = 1.0 / (1.0 + math.exp(-(time_since_novelty - 30.0) / 10.0))
        
        # Feature 3: Congestion level (from AIMD channel_busy metric)
        if hasattr(buoy, 'channel_busy_accum'):
            # Normalize by reasonable window (e.g., 20 seconds)
            congestion_level = min(buoy.channel_busy_accum / 20.0, 1.0)
        else:
            congestion_level = 0.0
        
        # Feature 4: Battery percent
        if hasattr(buoy, 'battery') and buoy.battery >= 0:
            # Assuming initial battery = 1000
            battery_percent = buoy.battery / 1000.0
        else:
            battery_percent = 1.0
        
        # Feature 5: Velocity magnitude (normalized)
        if hasattr(buoy, 'velocity'):
            vx, vy = buoy.velocity
            speed = math.hypot(vx, vy)
            velocity_magnitude = min(speed / default_velocity, 1.0)
        else:
            velocity_magnitude = 0.0
        
        # Feature 6: Reception rate trend
        # Count beacons received in last beacon_window_size seconds
        if hasattr(buoy, 'beacon_history_from_neighbor'):
            beacon_count = 0
            for neighbor_id, beacon_deque in buoy.beacon_history_from_neighbor.items():
                beacon_count += len(beacon_deque)
            
            # Normalize: max ~40 beacons in window (4 beacons per neighbor, ~10 neighbors)
            reception_rate_trend = min(beacon_count / 40.0, 1.0)
        else:
            reception_rate_trend = 0.0
        
        return ContextVector(
            neighbors_count=neighbors_count,
            time_since_novelty=time_since_novelty_norm,
            congestion_level=congestion_level,
            battery_percent=battery_percent,
            velocity_magnitude=velocity_magnitude,
            reception_rate_trend=reception_rate_trend,
        )


@dataclass
class ActionSpace:
    """
    Defines the action space: beacon send intervals.
    
    19 actions covering [0.25, 0.5, 0.75, 1.0, ..., 4.75, 5.0]
    """
    # Action index → interval in seconds
    intervals: List[float] = None
    
    def __post_init__(self):
        if self.intervals is None:
            # Generate 19 evenly spaced intervals from 0.25 to 5.0
            self.intervals = [0.25 + i * 0.25 for i in range(19)] # 0.25, 0.5, ..., 5.0 
            self.intervals = sorted(list(set(self.intervals)))  # Remove duplicates, sort
    
    def __len__(self) -> int:
        return len(self.intervals)
    
    def get_interval(self, action_idx: int) -> float:
        """Get interval (seconds) for action index."""
        if not 0 <= action_idx < len(self.intervals):
            raise ValueError(f"Invalid action index {action_idx}, must be in [0, {len(self.intervals)-1}]")
        return self.intervals[action_idx]
    
    def get_action(self, interval: float) -> int:
        """Get action index for desired interval (nearest match)."""
        idx = min(range(len(self.intervals)), key=lambda i: abs(self.intervals[i] - interval))
        return idx


@dataclass
class RewardCalculator:
    """
    Computes reward signal based on environment feedback.
    
    Reward components:
    1. Connectivity reward: # of neighbors sending beacons
    2. Reception reward: Rate at which we receive beacons
    3. Efficiency penalty: Energy cost of sending  
    4. Battery penalty: Low battery discouragement
    """
    
    def compute_reward(
        self,
        beacons_received_count: int,
        neighbors_sending: int,
        beacons_in_window: int,
        window_duration: float,
        energy_consumed: float,
        battery_percent: float,
        ideal_neighbors: int = 5,
    ) -> float:
        """
        Compute scalar reward from observation.
        
        Args:
            beacons_received_count: Number of beacons received in observation window
            neighbors_sending: Number of unique neighbors that sent in this window
            beacons_in_window: Total beacons we should expect (from all neighbors)
            window_duration: Length of observation window (seconds)
            energy_consumed: Energy spent on transmission in this interval
            battery_percent: Current battery level [0, 1]
            ideal_neighbors: Expected number of active neighbors
        
        Returns:
            Scalar reward (typically in [-1, 10] range)
        """
        # Component 1: Connectivity (0 to +4)
        # Reward if we hear from neighbors; penalty if silent
        neighbors_reward = min(neighbors_sending / ideal_neighbors * 4.0, 4.0)
        
        # Component 2: Reception rate (0 to +3)
        # Higher reception rate = better neighbor discovery
        if beacons_in_window > 0:
            reception_rate = beacons_received_count / beacons_in_window
            reception_reward = min(reception_rate * 3.0, 3.0)
        else:
            reception_reward = 0.0
        
        # Component 3: Energy efficiency penalty (-1 to 0)
        # Penalize excessive transmissions (energy > 0.1 J per second)
        energy_efficiency = energy_consumed / window_duration
        energy_penalty = min(energy_efficiency / 0.1, 1.0)  # Normalized to 0.1 J/s scale
        energy_penalty = -energy_penalty
        
        # Component 4: Battery penalty (0 to -2)
        # Strongly discourage operation with low battery
        if battery_percent < 0.2:
            battery_penalty = -2.0
        elif battery_percent < 0.5:
            battery_penalty = -1.0
        else:
            battery_penalty = 0.0
        
        # Total reward
        total_reward = neighbors_reward + reception_reward + energy_penalty + battery_penalty
        return total_reward
