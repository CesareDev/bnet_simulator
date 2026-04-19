"""
Contextual Multi-Armed Bandit RL Agent.

Thompson Sampling-based contextual bandit for learning optimal beacon intervals.
Each action (interval choice) maintains a posterior belief about its expected reward
given the current context.
"""

import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass, field
import json
import math

from .context import ContextVector, ActionSpace, RewardCalculator


@dataclass
class ArmBelief:
    """
    Posterior belief (Gaussian) over reward for a specific action (arm).
    
    Uses Normal-Inverse-Gamma conjugate prior for Bayesian regression.
    Maintains: mean reward, variance, and visit count for Thompson Sampling.
    """
    mean: float = 0.0              # μ: posterior mean reward
    variance: float = 1.0          # σ²: posterior variance
    precision: float = 1.0         # 1/σ²: inverse variance (for updates)
    visits: int = 0                # Number of times this action was selected
    sum_rewards: float = 0.0       # Σ rewards for this arm
    sum_sq_rewards: float = 0.0    # Σ rewards² (for variance tracking)
    
    def update(self, reward: float):
        """
        Update arm belief with observed reward (Bayesian online update).
        
        Uses running mean/variance update (Welford's algorithm).
        """
        self.visits += 1
        delta = reward - self.mean
        self.mean += delta / self.visits
        self.sum_rewards += reward
        self.sum_sq_rewards += reward ** 2
        
        # Update variance estimate
        if self.visits > 1:
            self.variance = max(
                (self.sum_sq_rewards - self.sum_rewards ** 2 / self.visits) / (self.visits - 1),
                0.01  # Minimum variance (avoid division by zero)
            )
            self.precision = 1.0 / self.variance
        else:
            self.variance = 1.0
            self.precision = 1.0
    
    def sample_thompson(self, rng: np.random.Generator) -> float:
        """
        Sample from posterior distribution for Thompson Sampling.
        Returns a single sample from N(μ, σ²).
        """
        return rng.normal(self.mean, math.sqrt(self.variance))


class ContextualBanditAgent:
    """
    Multi-Armed Bandit agent with contextual information.
    
    For each state context, maintains belief over reward distributions for
    each action. Uses Thompson Sampling to balance exploration/exploitation.
    
    The agent learns a mapping: context → action (send interval)
    that maximizes cumulative reward from beacon receptions.
    """
    
    def __init__(
        self,
        action_space: ActionSpace,
        context_dim: int = 6,
        learning_rate: float = 0.01,
        exploration_decay: float = 0.995,
        seed: int = 42,
    ):
        """
        Initialize the contextual bandit agent.
        
        Args:
            action_space: ActionSpace instance defining available intervals
            context_dim: Dimension of context vector (6 for our design)
            learning_rate: How much to weight new rewards vs. history
            exploration_decay: Decay factor for exploration (1.0 = no decay)
            seed: Random seed for Thompson Sampling
        """
        self.action_space = action_space
        self.context_dim = context_dim
        self.learning_rate = learning_rate
        self.exploration_decay = exploration_decay
        self.rng = np.random.default_rng(seed)
        
        # Arm beliefs: action_idx → ArmBelief
        self.arms: Dict[int, ArmBelief] = {
            i: ArmBelief() for i in range(len(action_space))
        }
        
        # Context-dependent beliefs (optional: for more sophisticated learning)
        # State hash → arm beliefs for that state
        self.context_arms: Dict[str, Dict[int, ArmBelief]] = {}
        
        # Reward function
        self.reward_calculator = RewardCalculator()
        
        # Tracking
        self.episode_count = 0
        self.total_rewards: List[float] = []
        self.action_history: List[Tuple[ContextVector, int, float]] = []  # (context, action, reward)
        self.last_context: Optional[ContextVector] = None
        self.last_action: Optional[int] = None
    
    def select_action(self, context: ContextVector, exploration: bool = True) -> int:
        """
        Select action (send interval) using Thompson Sampling.
        
        Args:
            context: Current context vector
            exploration: If False, use greedy action (exploit only)
        
        Returns:
            Action index (0 to len(action_space)-1)
        """
        if exploration:
            # Thompson Sampling: sample from each arm's posterior, pick max
            samples = {}
            for arm_idx, arm_belief in self.arms.items():
                samples[arm_idx] = arm_belief.sample_thompson(self.rng)
            
            best_action = max(samples, key=samples.get)
        else:
            # Greedy: pick action with highest mean reward
            best_action = max(self.arms, key=lambda idx: self.arms[idx].mean)
        
        self.last_context = context
        self.last_action = best_action
        
        return best_action
    
    def receive_reward(self, reward: float):
        """
        Observe reward for the last executed action and update beliefs.
        
        Args:
            reward: Scalar reward from environment
        """
        if self.last_action is None:
            return
        
        # Update global arm belief
        self.arms[self.last_action].update(reward)
        
        # Store in history
        if self.last_context is not None:
            self.action_history.append((self.last_context, self.last_action, reward))
            self.total_rewards.append(reward)
    
    def get_action_interval(self, action_idx: int) -> float:
        """Get the beacon interval (seconds) for an action index."""
        return self.action_space.get_interval(action_idx)
    
    def recommend_interval(self, context: ContextVector) -> float:
        """
        Recommend a beacon interval given context (convenience method).
        
        Returns:
            Interval in seconds
        """
        action = self.select_action(context, exploration=True)
        return self.get_action_interval(action)
    
    def get_arm_statistics(self) -> Dict[int, Dict[str, float]]:
        """
        Get summary statistics for all arms (for monitoring).
        
        Returns:
            Dict mapping action_idx → {mean, variance, visits, interval}
        """
        stats = {}
        for arm_idx, arm_belief in self.arms.items():
            stats[arm_idx] = {
                "interval_seconds": self.action_space.get_interval(arm_idx),
                "mean_reward": arm_belief.mean,
                "variance": arm_belief.variance,
                "visits": arm_belief.visits,
            }
        return stats
    
    def reset_episode(self):
        """Reset for new episode."""
        self.last_action = None
        self.last_context = None
        self.episode_count += 1
    
    def get_summary(self) -> Dict:
        """Get summary of learning progress."""
        if not self.total_rewards:
            avg_reward = 0.0
        else:
            avg_reward = sum(self.total_rewards) / len(self.total_rewards)
        
        return {
            "episode_count": self.episode_count,
            "total_actions": sum(arm.visits for arm in self.arms.values()),
            "average_reward": avg_reward,
            "arm_statistics": self.get_arm_statistics(),
            "recent_rewards": self.total_rewards[-20:] if self.total_rewards else [],
        }
    
    def save(self, filepath: str):
        """
        Save agent state to JSON.
        
        Args:
            filepath: Path to save to
        """
        state = {
            "episode_count": self.episode_count,
            "arms": {
                str(idx): {
                    "mean": arm.mean,
                    "variance": arm.variance,
                    "visits": arm.visits,
                    "sum_rewards": arm.sum_rewards,
                }
                for idx, arm in self.arms.items()
            },
            "total_rewards": self.total_rewards[-1000:],  # Keep last 1000
        }
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self, filepath: str):
        """
        Load agent state from JSON.
        
        Args:
            filepath: Path to load from
        """
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        self.episode_count = state["episode_count"]
        for idx, arm_data in state["arms"].items():
            idx = int(idx)
            self.arms[idx].mean = arm_data["mean"]
            self.arms[idx].variance = arm_data["variance"]
            self.arms[idx].visits = arm_data["visits"]
            self.arms[idx].sum_rewards = arm_data["sum_rewards"]
        self.total_rewards = state.get("total_rewards", [])
