"""
Experience Replay Buffer for RL agent.

Stores state-action-reward transitions for analysis and offline learning.
Provides utilities for batch processing and learning from experience.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from collections import deque
import json

from .context import ContextVector


@dataclass
class Transition:
    """
    Single state-action-reward transition from environment.
    """
    context: ContextVector
    action: int                    # Action index (0 to n_actions-1)
    reward: float
    next_context: Optional[ContextVector] = None
    terminated: bool = False       # Episode termination flag
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "context": self.context.to_array(),
            "action": self.action,
            "reward": self.reward,
            "next_context": self.next_context.to_array() if self.next_context else None,
            "terminated": self.terminated,
        }


class ReplayBuffer:
    """
    Circular buffer storing recent transitions.
    
    Useful for:
    - Analyzing agent behavior
    - Computing aggregate statistics
    - Potential for batch updates (future enhancement)
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize replay buffer.
        
        Args:
            max_size: Maximum number of transitions to store
        """
        self.max_size = max_size
        self.buffer: deque = deque(maxlen=max_size)
        self.episode_starts: List[int] = [0]  # Indices where episodes start
    
    def add(self, transition: Transition):
        """
        Add transition to buffer.
        
        Args:
            transition: Transition object to add
        """
        self.buffer.append(transition)
        
        # Track episode boundaries
        if transition.terminated:
            self.episode_starts.append(len(self.buffer))
    
    def __len__(self) -> int:
        return len(self.buffer)
    
    def sample_batch(self, batch_size: int) -> List[Transition]:
        """
        Sample random batch of transitions (uniform).
        
        Args:
            batch_size: Number of transitions to sample
        
        Returns:
            List of Transition objects
        """
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        
        import random
        return random.sample(list(self.buffer), batch_size)
    
    def get_recent(self, n: int) -> List[Transition]:
        """
        Get n most recent transitions.
        
        Args:
            n: Number of recent transitions
        
        Returns:
            List of Transition objects
        """
        return list(self.buffer)[-n:] if self.buffer else []
    
    def get_episode(self, episode_idx: int) -> Optional[List[Transition]]:
        """
        Get all transitions from a specific episode.
        
        Args:
            episode_idx: Episode index
        
        Returns:
            List of Transition objects, or None if invalid index
        """
        if episode_idx >= len(self.episode_starts) - 1:
            return None
        
        start = self.episode_starts[episode_idx]
        end = self.episode_starts[episode_idx + 1]
        
        return list(self.buffer)[start:end]
    
    def get_cumulative_reward(self, episode_idx: int) -> float:
        """
        Compute total reward for an episode.
        
        Args:
            episode_idx: Episode index
        
        Returns:
            Sum of rewards in episode
        """
        episode = self.get_episode(episode_idx)
        if episode is None:
            return 0.0
        return sum(t.reward for t in episode)
    
    def get_action_frequency(self) -> dict:
        """
        Count how often each action was selected.
        
        Returns:
            Dict mapping action_idx → count
        """
        freq = {}
        for transition in self.buffer:
            action = transition.action
            freq[action] = freq.get(action, 0) + 1
        return freq
    
    def get_reward_statistics(self) -> dict:
        """
        Compute statistics over rewards.
        
        Returns:
            Dict with min, max, mean, std.dev of rewards
        """
        if not self.buffer:
            return {"min": 0, "max": 0, "mean": 0, "std": 0, "count": 0}
        
        rewards = [t.reward for t in self.buffer]
        import statistics
        
        return {
            "min": min(rewards),
            "max": max(rewards),
            "mean": statistics.mean(rewards),
            "stdev": statistics.stdev(rewards) if len(rewards) > 1 else 0,
            "count": len(rewards),
        }
    
    def clear(self):
        """Clear all transitions."""
        self.buffer.clear()
        self.episode_starts = [0]
    
    def save(self, filepath: str):
        """
        Save buffer to JSON file.
        
        Args:
            filepath: Path to save to
        """
        data = {
            "transitions": [t.to_dict() for t in self.buffer],
            "episode_starts": self.episode_starts,
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: str):
        """
        Load buffer from JSON file.
        
        Args:
            filepath: Path to load from
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.buffer.clear()
        for t_dict in data["transitions"]:
            context = ContextVector(*t_dict["context"])
            next_context = ContextVector(*t_dict["next_context"]) if t_dict["next_context"] else None
            
            transition = Transition(
                context=context,
                action=t_dict["action"],
                reward=t_dict["reward"],
                next_context=next_context,
                terminated=t_dict["terminated"],
            )
            self.add(transition)
        
        self.episode_starts = data.get("episode_starts", [0])
