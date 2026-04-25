import random
import uuid
import math
from typing import Tuple, List, Optional, Dict
from config.config_handler import ConfigHandler
from utils import logging
from rl.rl_model import ContextualBanditAgent, ActionSpace
from rl.context import ContextVector, RewardCalculator
from rl.replay_buffer import ReplayBuffer, Transition

class BeaconScheduler:
    def __init__(self, mode, static_interval):
        cfg = ConfigHandler()
        
        self.min_interval = cfg.get('scheduler', 'beacon_min_interval')
        self.max_interval = cfg.get('scheduler', 'beacon_max_interval')
        self.static_interval = static_interval
        self.scheduler_type = mode
        self.default_velocity = cfg.get('buoys', 'default_velocity')
        
        self.last_static_send_time = -random.uniform(0, self.static_interval)
        self.last_dynamic_send_time = -random.uniform(0, self.min_interval)
        
        self.next_static_interval = self.static_interval
        self.next_dynamic_interval = None
        
        # RL Agent initialization
        self.rl_agent: Optional[ContextualBanditAgent] = None
        self.rl_replay_buffer: Optional[ReplayBuffer] = None
        self.rl_reward_calculator: Optional[RewardCalculator] = None
        self.last_rl_context: Optional[ContextVector] = None
        self.last_rl_action: Optional[int] = None
        
        # Tracking for reward computation
        self.beacon_window_start_time: float = 0.0
        self.beacons_received_in_window: int = 0
        self.neighbors_sent_in_window: set = set()
        self.energy_consumed_in_interval: float = 0.0
    
    def initialize_rl_agent(self, seed: int = 42):
        """Initialize RL agent for this scheduler."""
        action_space = ActionSpace()  # 19 actions: 0.25 to 5.0 seconds
        self.rl_agent = ContextualBanditAgent(
            action_space=action_space,
            context_dim=6,
            learning_rate=0.01,
            seed=seed,
        )
        self.rl_replay_buffer = ReplayBuffer(max_size=10000)
        self.rl_reward_calculator = RewardCalculator()
    
    def get_next_check_interval(self) -> float:
        if self.scheduler_type == "static":
            return self.static_interval
        else:
            return self.next_dynamic_interval if self.next_dynamic_interval is not None else self.min_interval

    def should_send(self, buoy, battery, velocity, neighbors, current_time):
        if self.scheduler_type == "static":
            return self.should_send_static(current_time)
        elif self.scheduler_type in ["dynamic_adab", "dynamic_acab"]:
            return self.should_send_dynamic(battery, velocity, neighbors, current_time)
        elif self.scheduler_type == "dynamic_aimd":
            return self.should_send_dynamic_aimd(buoy, current_time)
        elif self.scheduler_type == "rl":
            return self.should_send_rl(buoy, battery, velocity, neighbors, current_time)
        else:
            raise ValueError(f"Unknown scheduler type: {self.scheduler_type}")

    def should_send_static(self, current_time: float) -> bool:
        time_since_last = current_time - self.last_static_send_time
        logging.log_info(f"Static Scheduler: Time since last send: {time_since_last:.2f}s, Next interval: {self.next_static_interval:.2f}s")
        if time_since_last >= self.next_static_interval:
            self.last_static_send_time = current_time
            return True
        return False

    def should_send_dynamic(
        self,
        battery,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> bool:
        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)
        
        time_since_last = current_time - self.last_dynamic_send_time
        
        if time_since_last >= self.next_dynamic_interval:
            self.last_dynamic_send_time = current_time
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)
            #print(f'{self.next_dynamic_interval}')
            return True
        return False


    def should_send_dynamic_aimd(
        self,
        buoy,  # Pass the Buoy instance for local data #TODO: not sending buoy
        current_time: float,
    ) -> bool:
        # AIMD Congestion Detection
        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = 2 * self.min_interval
        aimd_mult = 1.5  # Multiplicative factor
        aimd_add = 0.3   # Additive decrease (seconds)

        num_neighbors = len(buoy.last_beacon_from_neighbor)

        # 1. Channel busy time (average)
        avg_busy = (buoy.channel_busy_accum / buoy.channel_busy_count) if buoy.channel_busy_count > 0 else 0.0
        busy_threshold = 0.001  # TODO: think about value

        # 2. Missing beacons from neighbors
        # Count only neighbors that have been actively sending (we have a short history)
        missing_neighbors = 0
        expected_interval = self.next_dynamic_interval if self.next_dynamic_interval is not None else self.min_interval
        for nid, last_time in buoy.last_beacon_from_neighbor.items():
            # Use per-neighbor history to decide if the neighbor recently stopped sending
            history = getattr(buoy, 'beacon_history_from_neighbor', {}).get(nid)
            if not history or len(history) < 3:
                # No sufficient history — treat as unknown, not missing
                continue

            times = list(history)
            expected_interval = max(expected_interval, times[-2] - times[-3])  # Use observed interval from history
            # Check the gap between the last two beacons recemeived from that neighbor
            last_gap = times[-1] - times[-2]
            # Compare that observed gap against our expected interval (not current time)
            if last_gap > aimd_mult * (expected_interval + max(self.static_interval, expected_interval)):
                missing_neighbors += 1

        # 3. My info in neighbor beacons (freshness)
        expected_interval = self.next_dynamic_interval if self.next_dynamic_interval is not None else self.min_interval
        outdated_count = 0
        for nid, (seen_time, my_info_ts) in buoy.my_info_in_neighbor.items():
            if my_info_ts is None:
                outdated_count += 1  # No info 
            elif buoy.my_beacon_timestamp - my_info_ts > aimd_mult * (expected_interval + max(self.static_interval, expected_interval)):
                outdated_count += 1  # Info is stale
        # Congestion if any metric is above threshold 
        # TODO: think if we need 3 options inc dec and no action
        num_neighbors = max(1, num_neighbors)  # Avoid division by zero
        congestion = (
            avg_busy > 0 or
            missing_neighbors / num_neighbors > 0.75 or
            outdated_count/num_neighbors > 0.75
        )

        

        if congestion:
            # Multiplicative increase of interval multiplicative decrease of rate
            self.next_dynamic_interval = min(self.max_interval, self.next_dynamic_interval * aimd_mult)
        else:
            # Additive decrease of interval additive increase of rate
            self.next_dynamic_interval = max(self.min_interval, self.next_dynamic_interval - aimd_add)        
        logging.log_debug(self.next_dynamic_interval)

        time_since_last = current_time - self.last_dynamic_send_time
        if time_since_last >= self.next_dynamic_interval:
            self.last_dynamic_send_time = current_time
            return True
        return False


    def should_send_dynamic_rl(
        self,
        buoy,
        battery,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> bool:
        """
        RL-based scheduler using contextual multi-armed bandit.
        
        Args:
            buoy: Buoy instance with full state
            battery: Battery level [0, max]
            velocity: (vx, vy) velocity tuple
            neighbors: List of (neighbor_id, last_seen_time, position)
            current_time: Current simulation time
        
        Returns:
            True if should transmit beacon now, False otherwise
        """
        if self.rl_agent is None:
            self.initialize_rl_agent()
        
        # Initialize beacon window on first call
        if self.beacon_window_start_time == 0.0:
            self.beacon_window_start_time = current_time
        
        # Extract context vector from current buoy state
        context = ContextVector.from_buoy_state(
            buoy,
            default_velocity=self.default_velocity,
            max_neighbors=60,
            beacon_window_size=10,
        )
        
        # Select action (send interval) using Thompson Sampling
        action_idx = self.rl_agent.select_action(context, exploration=True)
        next_interval = self.rl_agent.get_action_interval(action_idx)
        
        # Store for reward computation
        self.last_rl_context = context
        self.last_rl_action = action_idx
        
        # Check if it's time to send
        time_since_last = current_time - self.last_dynamic_send_time
        
        if time_since_last >= next_interval:
            # Time to send beacon
            self.last_dynamic_send_time = current_time
            
            # Compute reward for the interval that just completed
            window_duration = current_time - self.beacon_window_start_time
            reward = self.rl_reward_calculator.compute_reward(
                beacons_received_count=self.beacons_received_in_window,
                neighbors_sending=len(self.neighbors_sent_in_window),
                beacons_in_window=self.beacons_received_in_window + len(self.neighbors_sent_in_window),
                window_duration=max(window_duration, 0.01),  # Avoid division by zero
                energy_consumed=self.energy_consumed_in_interval,
                battery_percent=battery / 1000.0,  # Assuming max battery 1000
                ideal_neighbors=5,
            )
            
            # Update agent with reward
            self.rl_agent.receive_reward(reward)
            
            # Store transition in replay buffer
            if self.last_rl_context is not None:
                transition = Transition(
                    context=self.last_rl_context,
                    action=self.last_rl_action,
                    reward=reward,
                    next_context=context,
                    terminated=False,
                )
                self.rl_replay_buffer.add(transition)
            
            # Reset window for next interval
            self.beacon_window_start_time = current_time
            self.beacons_received_in_window = 0
            self.neighbors_sent_in_window = set()
            self.energy_consumed_in_interval = 0.0
            
            return True
        
        return False
    
    def should_send_rl(
        self,
        buoy,
        battery,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> bool:
        """Alias for should_send_dynamic_rl for consistency."""
        return self.should_send_dynamic_rl(buoy, battery, velocity, neighbors, current_time)
    
    def record_beacon_reception(self, neighbor_id: uuid.UUID):
        """Called when a beacon is received to update statistics."""
        self.beacons_received_in_window += 1
        self.neighbors_sent_in_window.add(neighbor_id)
    
    def record_energy_consumption(self, energy: float):
        """Called to record energy spent on transmission."""
        self.energy_consumed_in_interval += energy



    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        if self.scheduler_type == "dynamic_acab":
            n_neighbors = len(neighbors)
            NEIGHBORS_THRESHOLD = 10
            density_score = min(1.0, n_neighbors / NEIGHBORS_THRESHOLD)

            CONTACT_THRESHOLD = 20.0
            if neighbors:
                last_contact = max((ts for _, ts, _ in neighbors), default=current_time)
                delta = current_time - last_contact
                contact_score = max(0.0, 1.0 - (delta / CONTACT_THRESHOLD))
            else:
                contact_score = 0.0

            vx, vy = velocity
            speed = math.hypot(vx, vy)
            mobility_score = min(1.0, speed / self.default_velocity)

            w_density = 0.4
            w_contact = 0.3
            w_mobility = 0.3

            combined = (w_density * density_score + 
                       w_contact * contact_score + 
                       w_mobility * (1.0 - mobility_score))
        else:
            n_neighbors = len(neighbors)
            NEIGHBORS_THRESHOLD = 15
            density_score = min(1.0, n_neighbors / NEIGHBORS_THRESHOLD)
            combined = density_score

        fq = combined * combined
        bi = self.min_interval + fq * (self.max_interval - self.min_interval)

        jitter = random.uniform(-0.5, 0.5)
        bi_final = bi * (1 + jitter)

        return max(self.min_interval, min(bi_final, self.max_interval))
