"""
RL Module - Reinforcement Learning for Beacon Scheduling

This module implements a contextual multi-armed bandit system using Thompson Sampling
for learning optimal beacon transmission intervals in maritime ad-hoc networks.

Key Components:
- rl_model.py: ContextualBanditAgent (Thompson Sampling)
- context.py: State/action/reward definitions
- replay_buffer.py: Experience storage and statistics
- utils.py: Helper functions for normalization and reward estimation
"""

from .rl_model import ContextualBanditAgent, ActionSpace
from .context import ContextVector, ActionSpace, RewardCalculator
from .replay_buffer import ReplayBuffer, Transition
from . import utils

__all__ = [
    'ContextualBanditAgent',
    'ActionSpace',
    'ContextVector',
    'RewardCalculator',
    'ReplayBuffer',
    'Transition',
    'utils',
]
