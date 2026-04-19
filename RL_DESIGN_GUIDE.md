"""
REINFORCEMENT LEARNING FOR BEACON SCHEDULING - COMPLETE DESIGN GUIDE

================================================================================
TABLE OF CONTENTS
================================================================================
1. Overview
2. Problem Formulation
3. Algorithm Design (Thompson Sampling)
4. State Space (Context Vector)
5. Action Space
6. Reward Signal
7. Integration with Simulator
8. Configuration & Tuning
9. Monitoring & Evaluation
10. Code Examples

================================================================================
1. OVERVIEW
================================================================================

This RL system learns to optimize beacon transmission intervals in a maritime
ad-hoc network by observing:
- Network topology (number of neighbors)
- Channel conditions (congestion)
- Energy constraints (battery state)
- Mobility patterns (velocity)
- Network discovery indicator (time since new node found)

The system selects from 19 discrete beacon intervals and learns which intervals
maximize a composite reward metric combining connectivity, reception quality,
energy efficiency, and battery preservation.

================================================================================
2. PROBLEM FORMULATION
================================================================================

GOAL: Learn policy π: StateSpace → ActionSpace that maximizes cumulative reward

STATE SPACE:
  Continuous features from network observation
  - Network topology information
  - Link quality feedback
  - Energy status
  - Mobility information

ACTION SPACE:
  Discrete set of 19 beacon transmission intervals
  - Controls when and how frequently we announce presence

REWARD:
  Based on environment response (beacons from neighbors)
  - Direct feedback from network health
  - Not designer-specified heuristics

CONSTRAINTS:
  - Energy: Limited battery, must be preserved
  - Latency: Decisions made quickly (online learning)
  - Communication: Limited channel bandwidth

This is a CONTEXTUAL BANDIT problem because:
✓ Actions don't have delayed long-term effects (immediate feedback)
✓ Decision horizon is relatively short (beacon window)
✓ State space is high-dimensional (context features)
✓ Action space is moderate-sized (19 discrete values)

Therefore LSTM/temporal models are unnecessary.
Simpler Thompson Sampling is more appropriate than Deep Q-Learning.

================================================================================
3. ALGORITHM DESIGN - THOMPSON SAMPLING
================================================================================

THOMPSON SAMPLING:
  "Optimism under uncertainty" approach to exploration-exploitation

MECHANISM:
  For each action a ∈ {0, 1, ..., 18}:
    - Maintain posterior belief: p(R_a | history) ~ N(μ_a, σ²_a)
    - Sample r_a ~ N(μ_a, σ²_a)
    - Select action with max sampled r_a
  
  After observing reward r:
    - Update posterior: p(R_a | history ∪ {r})
    - Using online Bayesian update (Welford's algorithm)

ADVANTAGES:
  ✓ Principled exploration (probability matching)
  ✓ Fast convergence (sublinear regret bounds)
  ✓ Handles uncertainty naturally
  ✓ Scales to moderate action spaces
  ✓ Easy to parallelize (multiprocessing)
  ✓ Interpretable (mean/variance per action)

PSEUDOCODE:
  
  initialize: for each action a, belief ~ N(0, 1)
  
  for episode in range(num_episodes):
      observe state s from environment
      
      # Exploration via Thompson Sampling
      for action a in all_actions:
          sample θ_a ~ belief_a
      
      best_action = argmax_a θ_a
      
      # Execute and observe
      execute best_action
      receive reward r
      observe next_state s'
      
      # Update belief for selected action
      update belief_best_action with reward r
      store (s, a, r, s') in replay buffer
      
      s = s'

CONVERGENCE:
  - Regret: O(K log T) where K=#actions, T=time steps
  - Each action visited ~log(T) times asymptotically
  - After ~1000 steps, convergence to near-optimal policy

================================================================================
4. STATE SPACE - CONTEXT VECTOR
================================================================================

The context vector has 6 normalized features [0, 1]:

FEATURE 1: neighbors_count [0, 1]
  Raw: Number of 1-hop neighbors (0 to 60)
  Normalized: count / 60.0
  Clipped: min(normalized, 1.0)
  
  Meaning: Network density indicator
  - High value: Crowded network, need frequent updates
  - Low value: Isolated, can broadcast less often
  
  Source: from buoy.neighbors list
  Update frequency: Every scheduler check (~1s)

FEATURE 2: time_since_novelty [0, 1]
  Raw: Seconds since last new node discovered (0 to ∞)
  Normalized: sigmoid(t, inflection=30s, steepness=10s)
  Formula: 1 / (1 + exp(-(t - 30) / 10))
  
  Meaning: Network discovery phase indicator
  - High value: No new neighbors recently (steady state)
  - Low value: Active discovery phase (send alerts)
  
  Source: Max timestamp from buoy.discovered_nodes
  Update frequency: When new neighbors found
  
  Physical meaning:
  - First 10 seconds of discovery: aggressive broadcasts (low feature value)
  - After 30+ seconds: reduced broadcast rate (high feature value)

FEATURE 3: congestion_level [0, 1]
  Raw: Channel busy accumulation time (seconds)
  Normalized: min(channel_busy_accum / 20.0, 1.0)
  
  Meaning: Channel interference/congestion
  - High value: Channel crowded, back off
  - Low value: Channel clear, can transmit more
  
  Source: buoy.channel_busy_accum (from AIMD)
  Update frequency: Continuous (accumulated during MAC backoff)
  
  Physical meaning:
  - Measured via CSMA/CA backoff behavior
  - More backoff = more interference
  - Agent learns to reduce TX rate when congested

FEATURE 4: battery_percent [0, 1]
  Raw: Battery level (0 to 1000 mAh)
  Normalized: battery / 1000.0
  Clipped: [0, 1]
  
  Meaning: Energy availability
  - High value: Plenty of power, can transmit frequently
  - Low value: Limited power, must be conservative
  
  Source: buoy.battery
  Update frequency: Every event (energy model tracks consumption)
  
  Physical meaning:
  - Linear degradation over simulation
  - Below 0.2 (200 mAh): Strong penalty in reward
  - Below 0.05 (50 mAh): More severe penalty (shutdown warning)

FEATURE 5: velocity_magnitude [0, 1]
  Raw: Speed = sqrt(vx² + vy²) (0 to 30 m/s)
  Normalized: min(speed / 15.0, 1.0)
  
  Meaning: Mobility/node speed
  - High value: Fast moving, need frequent position updates
  - Low value: Stationary/slow, can update less often
  
  Source: buoy.velocity tuple (vx, vy)
  Update frequency: When position updates (every 1-5s)
  
  Physical meaning (from ACAB):
  - Faster nodes should broadcast more frequently
  - Others need fresh position info
  - Also affects neighbor discovery rate

FEATURE 6: reception_rate_trend [0, 1]
  Raw: Beacons received in last N seconds
  Normalized: min(beacon_count / 40.0, 1.0)
  
  Meaning: Received network feedback
  - High value: Many neighbors responding, good connectivity
  - Low value: Few responses, isolated or poor links
  
  Source: buoy.beacon_history_from_neighbor (per-neighbor deque)
  Update frequency: When beacons received
  
  Physical meaning:
  - Feedback indicator: are neighbors hearing us?
  - If low, increase TX rate to be heard
  - If high, neighbors are active, can reduce rate

NORMALIZATION DETAILS:

All features are clipped to [0, 1] to ensure agent sees bounded input.
This prevents extreme values from dominating decision:

  Feature values: [0.5, 0.2, 0.8, 1.0, 0.3, 0.6]
  Agent uses all features simultaneously

TYPICAL CONTEXT EXAMPLES:

1. Dense network discovery phase:
   [0.8, 0.1, 0.2, 0.9, 0.4, 0.7]
   → Many neighbors, new discoveries, clear channel, good battery
   → Agent likely selects LOW interval (frequent transmission)

2. Congested stable network:
   [0.9, 0.9, 0.8, 0.6, 0.1, 0.4]
   → Many neighbors, stable network, congested, decent battery
   → Agent likely selects MEDIUM interval (balance)

3. Mobile isolated node:
   [0.2, 0.5, 0.1, 0.3, 0.9, 0.2]
   → Few neighbors, moving fast, clear channel, low battery
   → Agent likely selects LOW interval (to announce presence + fast moving)

================================================================================
5. ACTION SPACE
================================================================================

ACTION SET: 19 discrete beacon transmission intervals

Intervals (seconds):
  [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 
   3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 4.75, 5.0]

Wait, that's 20 values. Let me correct to exactly 19:
  
  Action 0: 0.25s (very frequent)
  Action 1: 0.5s
  Action 2: 0.75s
  ...
  Action 18: 4.75s (very infrequent)
  Plus 5.0s as maximum

Actually, let me be precise:
  Number of intervals: 19
  Start: 0.25s
  Step: 0.25s
  End: 4.75s
  
  0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 
  2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 4.75

That's 19 actions covering 0.25-4.75, then 5.0 is often added as maximum.

RATIONALE FOR ACTION SET:
  - 0.25s: Upper bound for high-mobility mobile nodes
  - 5.0s: Lower bound for battery-constrained buoys
  - 0.25s step: Fine granularity (important for learning)
  - 19 actions: Computationally tractable for Thompson Sampling

INTERPRETATION:
  Lower action indices = more frequent transmissions
  Higher action indices = less frequent transmissions
  
  Agent learns context-dependent selection:
  - Dense network → higher action indices (less frequent)
  - Discovery phase → lower action indices (more frequent)
  - Low battery → higher action indices (conserve energy)
  - High velocity → lower action indices (frequent position updates)

================================================================================
6. REWARD SIGNAL DESIGN
================================================================================

REWARD COMPONENTS:

R_total = R_connectivity + R_reception + R_energy + R_battery

where:

(1) R_connectivity: Number of unique neighbors sending beacons
    
    Formula: min(neighbors_sending / ideal_neighbors * 4.0, 4.0)
    Range: [0, +4]
    Ideal neighbors: 5 (tunable)
    
    Interpretation:
    - 0 neighbors heard: R = 0 (silent network)
    - 5 neighbors heard: R = 4.0 (excellent)
    - 10 neighbors heard: R = 4.0 (saturates at max)
    
    Incentivizes: Maintaining connectivity, broadcasting regularly

(2) R_reception: Rate of beacon reception
    
    Formula: if beacons_expected > 0:
               min(beacons_received / beacons_expected * 3.0, 3.0)
             else:
               0.0
    
    Range: [0, +3]
    
    Interpretation:
    - Zero reception: R = 0
    - 100% of expected: R = 3.0 (good reception quality)
    - Partial reception: R = proportional
    
    Incentivizes: Maximizing message delivery success

(3) R_energy: Penalty for transmitting too frequently
    
    Formula: -(energy_per_second / 0.1)
    Range: [-1, 0]
    Baseline: 0.1 J/s
    
    Interpretation:
    - Light transmission (low energy): R ≈ 0
    - Heavy transmission (0.1 J/s): R ≈ -1
    - Very heavy (0.2 J/s): R = -2 (saturates below -1)
    
    Incentivizes: Energy efficiency, not just raw transmission rate

(4) R_battery: Penalty for low battery
    
    Formula: if battery_percent < 0.2:
               -2.0
             elif battery_percent < 0.5:
               -1.0
             else:
               0.0
    
    Range: [-2, 0]
    Critical threshold: 20% (200 mAh of 1000)
    Warning threshold: 50% (500 mAh)
    
    Interpretation:
    - High battery (>50%): R = 0 (no penalty)
    - Medium battery (20-50%): R = -1 (moderate penalty)
    - Low battery (<20%): R = -2 (severe penalty)
    
    Incentivizes: Preserving battery for long-term operation

TYPICAL REWARD EXAMPLES:

Scenario 1: Good connectivity, efficient, full battery
  R = 4 + 3 + 0 + 0 = +7 (EXCELLENT)
  Context: Dense network, good reception, not transmitting constantly, good power
  Agent reinforces this action positively

Scenario 2: Poor connectivity, some reception, low battery
  R = 0 + 1 + (-0.5) + (-1) = -0.5 (BAD)
  Context: Isolated, few beacons received, low power
  Agent stops selecting this action

Scenario 3: Medium connectivity, medium energy, very low power
  R = 2 + 1.5 + (-0.8) + (-2) = +0.7 (OK, but not great)
  Context: Some neighbors, decent efficiency, critical power
  Agent learns to be conservative here

REWARD OBSERVATION WINDOW:
  - Computed over each beacon interval
  - For action a with interval t_a seconds:
    - T_window = [T_send, T_send + t_a)
    - Count received beacons in F_window
    - Sum energy consumed in window
    - Reward = f(window_metrics)
  - Delayed feedback, but meaningful for convergence

REWARD NOISE:
  - Reception is stochastic (packet loss)
  - Congestion varies randomly
  - Battery consumption can vary
  - Reward M(a|s) = E[R | action a, state s] + noise
  - Thompson Sampling handles noise via posterior variance

================================================================================
7. INTEGRATION WITH SIMULATOR - STEP BY STEP
================================================================================

STEP 1: Prepare Buoy class to use RL scheduler

File: src/buoys/buoy.py

    # In Buoy.__init__, initialize scheduler:
    self.scheduler = BeaconScheduler()
    self.scheduler.scheduler_type = "rl"  # Instead of "static" or "dynamic_acab"
    self.scheduler.initialize_rl_agent(seed=42)

STEP 2: Call RL scheduler in event handler

File: src/buoys/buoy.py, in _handle_scheduler_check():

    def _handle_scheduler_check(self, event):
        should_send = self.scheduler.should_send(
            buoy=self,
            battery=self.battery,
            velocity=self.velocity,
            neighbors=self.neighbors,
            current_time=self.simulator.current_time,
        )
        
        if should_send:
            # Queue transmission
            self.simulator.schedule_event(
                EventType.TRANSMISSION_START,
                time=self.simulator.current_time,
                buoy_id=self.id,
                data={'beacon': self.create_beacon()}
            )

STEP 3: Record reception events

File: src/buoys/buoy.py, in _handle_reception():

    def _handle_reception(self, event):
        beacon = event.beacon
        sender_id = beacon.sender_id
        
        # Record for RL reward computation
        if self.scheduler.scheduler_type == "rl":
            self.scheduler.record_beacon_reception(sender_id)
        
        # Update neighbor list
        self.neighbors.append((sender_id, self.simulator.current_time, beacon.position))
        ...

STEP 4: Record energy consumption

File: src/buoys/buoy.py, in _handle_transmission_start():

    def _handle_transmission_start(self, event):
        # Record transmission energy for RL
        transmission_energy = 0.0044  # Joules from config
        if self.scheduler.scheduler_type == "rl":
            self.scheduler.record_energy_consumption(transmission_energy)
        
        # Consume battery
        self.battery -= transmission_energy
        ...

STEP 5: Configure to use RL in config.yaml

File: config.yaml

    simulation:
        schedulers: ['static', 'dynamic_adab', 'dynamic_acab', 'dynamic_aimd', 'rl']
        # Add 'rl' to list of active schedulers
    
    rl:
        enabled: true
        seed: 42
        learning_rate: 0.01
        exploration_decay: 0.995

STEP 6: Run simulation with RL

File: src/run.py (or your main simulation script)

    from src.config.config_handler import ConfigHandler
    
    cfg = ConfigHandler()
    
    # Create buoys with RL scheduler
    buoy = Buoy(position=(x, y), scheduler_type="rl")
    
    # Run simulation
    simulator.run(duration=3600.0)  # 1 hour
    
    # Access RL statistics
    rl_agent = buoy.scheduler.rl_agent
    summary = rl_agent.get_summary()
    print(f"Average reward: {summary['average_reward']:.2f}")
    print(f"Total actions: {summary['total_actions']}")

================================================================================
8. CONFIGURATION & TUNING
================================================================================

PARAMETERS:

(A) ActionSpace:
    - n_actions: 19 (fixed, covers 0.25-5.0s)
    - Can modify in context.py ActionSpace.__post_init__()
    
    Example: For finer control, use 39 actions (0.125s granularity)

(B) ContextVector normalization:
    - neighbors_count: max_neighbors = 60, can adjust to 100
    - time_since_novelty: sigmoid(inflection=30s, width=10s), tune for your network
    - congestion_level: window = 20s, scale = 0.1 J/s, tune for your mac
    - battery_percent: assumes 1000 mAh initial, adjust if different
    - velocity_magnitude: default_velocity = 15 m/s, adjust per vehicle
    - reception_rate_trend: window = 40 beacons max, tune per network size

(C) Reward calculator:
    - Weights: [4.0, 3.0, 1.0, 2.0] for [connectivity, reception, energy, battery]
    - Can adjust weights to prioritize different objectives
    
    More battery-critical: increase battery penalty weights
    More performance-critical: increase connectivity weight

(D) Thompson Sampling:
    - Learning rate: 0.01 (controls update speed)
    - Variance initialization: 1.0 per arm
    - Higher variance = more exploration initially
    
    For faster convergence: increase learning_rate to 0.05
    For more exploration: initialize variance = 2.0

(E) Replay buffer:
    - max_size: 10000 (sufficient for long runs)
    - Can increase to 100000 for multi-day simulations

TUNING STRATEGY:

1. Start with defaults (all hyperparameters as-is)
2. Run 1-hour simulation, check average reward
3. If reward < 2.0: increase connectivity weight, decrease energy penalty
4. If reward > 8.0: increase energy penalty, ensure sufficient exploration
5. If actions are stuck on same interval: increase variance, decrease learning_rate
6. If battery is depleting too fast: increase battery penalty weights

TYPICAL GOOD CONFIGURATION (Maritime buoys):

    ActionSpace: 19 actions, 0.25-5.0s
    Context: All 6 features included
    Reward weights: [4.0, 3.0, 1.0, 2.0]
    Learning rate: 0.01
    Seed: 42
    Episodes: 100+ for convergence

================================================================================
9. MONITORING & EVALUATION
================================================================================

STATISTICS TO TRACK:

(1) Episode Metrics:
    - Total episode reward: sum of all step rewards
    - Average step reward: mean of step rewards
    - Episode length: number of beacon transmissions
    - Max/min rewards: performance range

(2) Agent Learning:
    - Average reward trend: should increase over time
    - Action selection frequency: entropy of action distribution
    - Belief uncertainty: mean posterior variance per arm
    
(3) Action Performance:
    - Mean reward per action: which intervals work best?
    - Visits per action: is exploration adequate?
    - Win rate per action: fraction of time action is selected
    
(4) Network Metrics:
    - Neighbor discovery rate: new neighbors per hour
    - Reception rate: fraction of expected beacons received
    - Collision rate: beacons lost due to congestion
    - Energy efficiency: energy per neighbor maintained

VISUALIZATION:

```python
import matplotlib.pyplot as plt

# Plot 1: Learning curve
agent = buoy.scheduler.rl_agent
plt.figure(figsize=(15, 5))

plt.subplot(1, 3, 1)
rewards = agent.total_rewards
window_size = 20
smoothed = [sum(rewards[i:i+window_size])/window_size 
            for i in range(len(rewards)-window_size)]
plt.plot(smoothed)
plt.xlabel("Steps")
plt.ylabel("Avg Reward (20-step window)")
plt.title("Learning Progress")
plt.grid()

# Plot 2: Action selection distribution
stats = agent.get_arm_statistics()
action_visits = [stat['visits'] for stat in stats.values()]
intervals = [stat['interval_seconds'] for stat in stats.values()]
plt.subplot(1, 3, 2)
plt.bar(intervals, action_visits)
plt.xlabel("Beacon Interval (s)")
plt.ylabel("Visit Count")
plt.title("Action Selection Frequency")

# Plot 3: Reward per action
action_rewards = [stat['mean_reward'] for stat in stats.values()]
plt.subplot(1, 3, 3)
plt.bar(intervals, action_rewards)
plt.xlabel("Beacon Interval (s)")
plt.ylabel("Mean Reward")
plt.title("Action Quality")

plt.tight_layout()
plt.savefig("rl_training_stats.png")
```

CONVERGENCE INDICATORS:

✓ Reward converges: moving average plateaus
✓ Action entropy decreases: fewer actions dominate
✓ Winning action emerges: 1-2 intervals get majority visits
✓ Variance decreases: posterior becomes more confident

Expected convergence time: 1000-2000 steps (16-30 minutes real time)

================================================================================
10. CODE EXAMPLES
================================================================================

EXAMPLE 1: Initialize RL agent for a single buoy

```python
from src.protocols.scheduler import BeaconScheduler
from src.rl.context import ContextVector

# Create scheduler with RL
scheduler = BeaconScheduler()
scheduler.scheduler_type = "rl"
scheduler.initialize_rl_agent(seed=42)

# Use in scheduler check
context = ContextVector.from_buoy_state(buoy)
action = scheduler.rl_agent.select_action(context)
interval = scheduler.rl_agent.get_action_interval(action)
print(f"Next beacon interval: {interval:.2f}s")
```

EXAMPLE 2: Evaluate trained agent

```python
# Load saved agent
scheduler.rl_agent.load("trained_agent.json")
summary = scheduler.rl_agent.get_summary()

print(f"Episodes trained: {summary['episode_count']}")
print(f"Total actions: {summary['total_actions']}")
print(f"Average reward: {summary['average_reward']:.2f}")

# Find best action
best_action = max(summary['arm_statistics'], 
                  key=lambda idx: summary['arm_statistics'][idx]['mean_reward'])
best_interval = summary['arm_statistics'][best_action]['interval_seconds']
print(f"Best learned interval: {best_interval:.2f}s")
```

EXAMPLE 3: Compare multiple agents

```python
from src.rl.rl_model import ContextualBanditAgent, ActionSpace

# Train agents with different seeds
agents = {}
for seed in [42, 123, 456]:
    agent = ContextualBanditAgent(ActionSpace(), seed=seed)
    # ... run simulation ...
    agents[seed] = agent

# Compare final performance
for seed, agent in agents.items():
    summary = agent.get_summary()
    print(f"Seed {seed}: avg_reward = {summary['average_reward']:.2f}")

# Ensemble: vote on action
context = ContextVector(...)
votes = [agent.select_action(context, exploration=False) for agent in agents.values()]
best_action = max(set(votes), key=votes.count)  # plurality vote
```

EXAMPLE 4: Analyze exploration vs exploitation

```python
from src.rl.utils import action_diversity_score

# After training, check if exploration was adequate
action_freq = rl_agent.rl_replay_buffer.get_action_frequency()
diversity = action_diversity_score(action_freq, len(ActionSpace()))

if diversity > 0.7:
    print("Good exploration - agent tried many actions")
elif diversity < 0.3:
    print("Poor exploration - agent stuck on few actions")
    print("  Increase variance or decrease learning_rate")

# Check action quality distribution
stats = rl_agent.get_arm_statistics()
rewards = [stat['mean_reward'] for stat in stats.values()]
print(f"Reward std.dev: {statistics.stdev(rewards):.2f}")
print(f"Reward range: [{min(rewards):.2f}, {max(rewards):.2f}]")
```

================================================================================
SUMMARY & QUICK START
================================================================================

1. Copy RL module files to src/rl/
2. Update src/protocols/scheduler.py with RL integration
3. Set buoy.scheduler.scheduler_type = "rl"
4. Call scheduler.initialize_rl_agent()
5. Call scheduler.record_beacon_reception() and record_energy_consumption()
6. Run simulation
7. Monitor agent.get_summary() for learning progress
8. Save trained agent: agent.save("trained_rl_beacon.json")

For detailed usage: See rl_example_usage.py

Questions or modifications? Adapt reward weights and context features to match
your specific network characteristics and objectives.

================================================================================
"""
