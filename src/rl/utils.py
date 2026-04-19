"""
RL utilities and helper functions.
"""

import math
from typing import Tuple, List
import numpy as np


def normalize_context(
    raw_context: Tuple[float, ...],
    mins: Tuple[float, ...] = None,
    maxs: Tuple[float, ...] = None,
) -> Tuple[float, ...]:
    """
    Normalize context features to [0, 1] range using min-max scaling.
    
    Args:
        raw_context: Tuple of feature values
        mins: Minimum values for each feature (defaults to 0)
        maxs: Maximum values for each feature (defaults to 1)
    
    Returns:
        Normalized context tuple
    """
    if mins is None:
        mins = tuple([0.0] * len(raw_context))
    if maxs is None:
        maxs = tuple([1.0] * len(raw_context))
    
    normalized = []
    for val, min_val, max_val in zip(raw_context, mins, maxs):
        if max_val == min_val:
            normalized.append(0.0)
        else:
            norm_val = (val - min_val) / (max_val - min_val)
            normalized.append(max(0.0, min(1.0, norm_val)))  # Clip to [0, 1]
    
    return tuple(normalized)


def compute_smooth_reward(
    current_reward: float,
    previous_reward: float,
    alpha: float = 0.3,
) -> float:
    """
    Smooth reward signal using exponential moving average.
    Helps reduce noise in reward signal.
    
    Args:
        current_reward: Latest observed reward
        previous_reward: Previously smoothed reward
        alpha: Smoothing factor (0 to 1), higher = more weight on current
    
    Returns:
        Smoothed reward
    """
    return alpha * current_reward + (1.0 - alpha) * previous_reward


def entropy_of_action_distribution(
    action_counts: dict,
    n_actions: int,
) -> float:
    """
    Compute Shannon entropy of action selection distribution.
    
    High entropy = agent explores uniformly
    Low entropy = agent exploits specific actions
    
    Args:
        action_counts: Dict mapping action_idx → visit count
        n_actions: Total number of actions
    
    Returns:
        Entropy value (0 to log(n_actions))
    """
    total = sum(action_counts.values())
    if total == 0:
        return math.log(n_actions)
    
    entropy = 0.0
    for count in action_counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log(p)
    
    return entropy


def action_diversity_score(
    action_counts: dict,
    n_actions: int,
) -> float:
    """
    Normalized entropy-based diversity score [0, 1].
    
    0 = only one action used
    1 = perfect uniform exploration
    
    Args:
        action_counts: Dict mapping action_idx → visit count
        n_actions: Total number of actions
    
    Returns:
        Diversity score in [0, 1]
    """
    max_entropy = math.log(n_actions)
    current_entropy = entropy_of_action_distribution(action_counts, n_actions)
    
    if max_entropy == 0:
        return 1.0
    
    return current_entropy / max_entropy


def estimate_optimal_interval(
    neighbor_count: int,
    congestion_level: float,
    velocity: float,
    default_velocity: float = 15.0,
) -> float:
    """
    Heuristic estimate of optimal beacon interval (baseline for RL to learn from).
    
    Combines principles from ACAB (density, contact, velocity).
    
    Args:
        neighbor_count: Number of neighbors
        congestion_level: Channel congestion [0, 1]
        velocity: Current velocity magnitude
        default_velocity: Normalization factor
    
    Returns:
        Estimated interval in seconds [0.25, 5.0]
    """
    # Use ACAB-like formula
    density_score = min(neighbor_count / 10.0, 1.0)  # 10 neighbors = saturation
    congestion_score = congestion_level
    velocity_score = min(velocity / default_velocity, 1.0)
    
    # Combine: send more frequently if moving, others are active, channel free
    combined = (0.4 * density_score + 
                0.3 * (1.0 - congestion_score) + 
                0.3 * velocity_score)
    
    # Map to interval
    min_interval = 0.25
    max_interval = 5.0
    fq = combined * combined
    interval = min_interval + fq * (max_interval - min_interval)
    
    # Add small random jitter
    import random
    interval = interval * (1.0 + random.uniform(-0.1, 0.1))
    
    return max(min_interval, min(interval, max_interval))
