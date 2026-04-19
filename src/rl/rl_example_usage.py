"""
RL Design Documentation and Integration Guide

CONTEXTUAL MULTI-ARMED BANDIT FOR BEACON SCHEDULING
=====================================================

This implementation provides a Thompson Sampling-based contextual multi-armed 
bandit system for learning optimal beacon send intervals in a maritime Ad Hoc network.

ARCHITECTURE OVERVIEW
====================

1. STATE SPACE (Context Vector)
   - neighbors_count: Number of 1-hop neighbors [0, 60] normalized
   - time_since_novelty: Seconds since new node discovered, sigmoid normalized
   - congestion_level: Channel busy time ratio [0, 1]
   - battery_percent: Battery level as fraction [0, 1]
   - velocity_magnitude: Speed normalized to default_velocity [0, 1]
   - reception_rate_trend: Beacons received in recent window [0, 1]

2. ACTION SPACE
   - 19 discrete actions
   - Each action represents a beacon send interval
   - Intervals: {0.25, 0.5, 0.75, 1.0, 1.25, ..., 4.75, 5.0} seconds
   - These align with simulator config (1-5s was original, but we expand to 0.25-5.0s)

3. REWARD SIGNAL
   R(t) = R_connectivity + R_reception + R_energy + R_battery
   
   where:
   - R_connectivity [0, +4]: Number of neighbors sending beacons
   - R_reception [0, +3]: Rate of beacon reception from neighbors  
   - R_energy [-1, 0]: Penalty based on transmission power consumption
   - R_battery [0, -2]: Penalty for low battery (< 20%), more severe < 5%
   
   Total reward typically ranges [-1, +10]

4. LEARNING ALGORITHM
   - Thompson Sampling: Maintains Bayesian posterior belief (Gaussian) over 
     reward for each action
   - For each action a: belief ~ N(μ_a, σ²_a)
   - Selection: Sample from each posterior, choose action with max sample
   - Update: Online Bayesian update using Welford's algorithm after observing reward
   - Naturally balances exploration vs exploitation

KEY DESIGN DECISIONS
====================

1. Why Multi-Armed Bandit (vs Deep Q-Learning)?
   ✓ Proven effective for small action spaces (19 actions)
   ✓ No neural network needed - interpretable, fast
   ✓ Works with continuous/high-dimensional state (context)
   ✓ Thompson Sampling gives optimism under uncertainty
   ✓ Simpler to tune than DQN, no target networks needed
   ✓ Naturally handles changing reward distributions

2. Why Context Features?
   - neighbors_count: Load indicator - crowded networks need different strategies
   - time_since_novelty: Network discovery phase vs steady state
   - congestion_level: Interference detection - reduce TX when congested
   - battery_percent: Energy-aware system - degrade gracefully
   - velocity_magnitude: Mobility awareness (inspired by ACAB)
   - reception_rate_trend: Feedback confirmation - are neighbors hearing us?

3. Why Reward Structure?
   - Connectivity bonus: Directly incentivizes neighbor discovery
   - Reception reward: Indirect measure that our broadcasts reach neighbors
   - Energy penalty: Forces efficiency, not just max broadcast rate
   - Battery penalty: Prevents energy depletion (critical for at-sea buoys)

4. Window-Based Rewards
   - Reward computed over the beacon interval period
   - Captures delayed effects (neighbor response time)
   - Realistic for maritime networks with high latency/packet loss

INTEGRATION WITH SIMULATOR
===========================

1. Modify Buoy.__init__ to set scheduler_type="rl":
   
   scheduler = BeaconScheduler()
   scheduler.scheduler_type = "rl"
   scheduler.initialize_rl_agent(seed=42)

2. In Buoy event handlers, trigger RL scheduler:
   
   def _handle_scheduler_check(self, event):
       should_send = self.scheduler.should_send(
           self, self.battery, self.velocity, 
           self.neighbors, event.time
       )

3. When receiving beacons, record it:
   
   def _handle_reception(self, event):
       beacon = event.beacon
       self.scheduler.record_beacon_reception(beacon.sender_id)

4. Track energy consumption:
   
   def _handle_transmission_start(self, event):
       energy = 0.0044  # Config: transmission_energy
       self.scheduler.record_energy_consumption(energy)

USAGE EXAMPLE
=============

See: rl_example_usage.py

MONITORING & ANALYSIS
=====================

During training, monitor:
- Average reward per episode
- Action selection distribution (entropy)
- Mean reward per action
- Variance per action (uncertainty)
- Recent rewards (smoothed via EMA)

"""

# Example of how to use the RL system in simulation

from .rl_model import ContextualBanditAgent, ActionSpace
from .context import ContextVector, RewardCalculator
from .replay_buffer import ReplayBuffer, Transition
from .utils import action_diversity_score
import numpy as np


def example_single_action_selection():
    """Demonstrate action selection given a context."""
    
    # Initialize agent
    action_space = ActionSpace()  # 19 actions
    agent = ContextualBanditAgent(
        action_space=action_space,
        context_dim=6,
        learning_rate=0.01,
        seed=42,
    )
    
    # Create a sample context
    context = ContextVector(
        neighbors_count=0.5,        # 30 neighbors out of 60
        time_since_novelty=0.2,     # Low novelty window
        congestion_level=0.3,       # Some congestion
        battery_percent=0.8,        # Good battery
        velocity_magnitude=0.4,     # Moderate movement
        reception_rate_trend=0.6,   # Decent reception
    )
    
    # Select action
    action = agent.select_action(context, exploration=True)
    interval = agent.get_action_interval(action)
    
    print(f"Selected action: {action}, Interval: {interval:.2f}s")
    
    # Simulate some rewards
    for _ in range(5):
        reward = np.random.normal(2.0, 1.0)  # Mean reward 2.0, std 1.0
        agent.receive_reward(reward)
        
        # Get new context and select next action
        context = ContextVector(
            neighbors_count=np.random.uniform(0, 1),
            time_since_novelty=np.random.uniform(0, 1),
            congestion_level=np.random.uniform(0, 1),
            battery_percent=0.7,  # Battery declining
            velocity_magnitude=np.random.uniform(0, 1),
            reception_rate_trend=np.random.uniform(0, 1),
        )
        
        action = agent.select_action(context, exploration=True)
        interval = agent.get_action_interval(action)
        print(f"Action: {action}, Interval: {interval:.2f}s, Last Reward: {reward:.2f}")
    
    # Print summary
    print("\n=== Agent Summary ===")
    summary = agent.get_summary()
    print(f"Episodes: {summary['episode_count']}")
    print(f"Total actions taken: {summary['total_actions']}")
    print(f"Average reward: {summary['average_reward']:.2f}")
    print(f"\nTop 5 successful actions:")
    stats = summary['arm_statistics']
    top_actions = sorted(stats.items(), key=lambda x: x[1]['mean_reward'], reverse=True)[:5]
    for idx, stat in top_actions:
        print(f"  Action {idx}: Interval={stat['interval_seconds']:.2f}s, "
              f"Mean={stat['mean_reward']:.2f}, Visits={stat['visits']}")


def example_training_episode():
    """Simulate a full training episode with multiple decisions."""
    
    agent = ContextualBanditAgent(ActionSpace(), seed=42)
    reward_calculator = RewardCalculator()
    replay_buffer = ReplayBuffer(max_size=10000)
    
    # Simulate 50 time steps
    episode_rewards = []
    
    for step in range(50):
        # Generate context (simulating network conditions)
        neighbors = np.random.poisson(10)  # Poisson arrival
        congestion = np.random.beta(2, 5)  # More low congestion
        battery = max(0.1, 1.0 - step / 100)  # Battery declining
        
        context = ContextVector(
            neighbors_count=min(neighbors / 60, 1.0),
            time_since_novelty=np.random.uniform(0, 1),
            congestion_level=congestion,
            battery_percent=battery,
            velocity_magnitude=np.random.uniform(0, 0.5),
            reception_rate_trend=np.random.uniform(0.3, 1.0),
        )
        
        # Agent selects action
        action = agent.select_action(context, exploration=True)
        interval = agent.get_action_interval(action)
        
        # Environment provides reward
        # Better rewards when neighbors are present and battery is good
        reward_components = {
            'neighbors': 2.0 if neighbors > 5 else 1.0,
            'battery': 0.0 if battery < 0.2 else 0.0,
            'congestion': -0.5 if congestion > 0.5 else 0.0,
        }
        reward = sum(reward_components.values()) + np.random.normal(0, 0.5)
        
        # Agent learns
        agent.receive_reward(reward)
        episode_rewards.append(reward)
        
        # Store in replay buffer
        next_context = ContextVector(
            neighbors_count=np.random.uniform(0, 1),
            time_since_novelty=np.random.uniform(0, 1),
            congestion_level=np.random.uniform(0, 1),
            battery_percent=battery - 0.01,
            velocity_magnitude=np.random.uniform(0, 1),
            reception_rate_trend=np.random.uniform(0, 1),
        )
        
        transition = Transition(
            context=context,
            action=action,
            reward=reward,
            next_context=next_context,
            terminated=(step == 49),
        )
        replay_buffer.add(transition)
    
    # Print results
    print(f"Episode total reward: {sum(episode_rewards):.2f}")
    print(f"Episode average reward: {sum(episode_rewards) / len(episode_rewards):.2f}")
    print(f"Replay buffer size: {len(replay_buffer)}")
    
    # Action diversity
    action_freq = replay_buffer.get_action_frequency()
    diversity = action_diversity_score(action_freq, len(ActionSpace().intervals))
    print(f"Action diversity score: {diversity:.2f} (0=no diversity, 1=perfect)")
    print(f"Reward statistics: {replay_buffer.get_reward_statistics()}")


if __name__ == "__main__":
    print("=" * 60)
    print("RL BEACON SCHEDULER - EXAMPLE USAGE")
    print("=" * 60)
    
    print("\n# Example 1: Single Action Selection\n")
    example_single_action_selection()
    
    print("\n" + "=" * 60)
    print("\n# Example 2: Training Episode\n")
    example_training_episode()
    
    print("\n" + "=" * 60)
    print("Done!")
