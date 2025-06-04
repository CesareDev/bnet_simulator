import os
import csv
from bnet_simulator.utils import logging, config

class Metrics:
    def __init__(self):
        self.beacons_sent = 0
        self.beacons_received = 0
        self.beacons_lost = 0
        self.beacons_collided = 0
        self.total_latency = 0.0
        self.discovery_times = {}
        self.reaction_latencies = []
        self.delivered_beacons = set()
        self.scheduler_latencies = []

    def log_sent(self):
        self.beacons_sent += 1

    def log_received(self, sender_id, timestamp, receive_time, receiver_id=None):
        key = (sender_id, timestamp)
        if key not in self.delivered_beacons:
            self.beacons_received += 1
            self.delivered_beacons.add(key)
            self.total_latency += receive_time - timestamp

            if receiver_id is not None:
                if receiver_id not in self.discovery_times:
                    self.discovery_times[receiver_id] = {}
                if sender_id not in self.discovery_times[receiver_id]:
                    latency = receive_time - timestamp
                    self.reaction_latencies.append(latency)
                    self.discovery_times[receiver_id][sender_id] = receive_time

    def log_lost(self):
        self.beacons_lost += 1

    def log_collision(self):
        self.beacons_collided += 1

    def record_scheduler_latency(self, latency: float):  # NEW
        self.scheduler_latencies.append(latency)

    def avg_scheduler_latency(self) -> float:  # NEW
        return sum(self.scheduler_latencies) / len(self.scheduler_latencies) if self.scheduler_latencies else 0.0

    def summary(self, sim_time: float):
        avg_latency = self.total_latency / self.beacons_received if self.beacons_received else 0
        return {
            "Scheduler Type": config.SCHEDULER_TYPE,
            "World Size": f"{config.WORLD_WIDTH}x{config.WORLD_HEIGHT}",
            "Mobile Buoys": config.MOBILE_BUOY_COUNT,
            "Fixed Buoys": config.FIXED_BUOY_COUNT,
            "Simulation Duration": config.SIMULATION_DURATION,
            "Sent": self.beacons_sent,
            "Received": self.beacons_received,
            "Lost": self.beacons_lost,
            "Collisions": self.beacons_collided,
            "Avg Latency": avg_latency,
            "Avg Scheduler Latency": self.avg_scheduler_latency(),  # NEW
            "Delivery Ratio": self.beacons_received / self.beacons_sent if self.beacons_sent else 0,
            "Collision Rate": self.beacons_collided / self.beacons_sent if self.beacons_sent else 0,
            "Avg Reaction Latency": (
                sum(self.reaction_latencies) / len(self.reaction_latencies)
                if self.reaction_latencies else 0
            ),
            "Throughput (beacons/sec)": (
                self.beacons_received / sim_time
                if sim_time > 0 else 0
            ),
        }

    def export_metrics_to_csv(self, summary, filename=None):
        # Ensure results directory exists at the project root (one level up from src)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        results_dir = os.path.join(project_root, "simulation_results")
        os.makedirs(results_dir, exist_ok=True)

        # Build a unique filename if not provided
        if filename is None:
            filename = (
                f"{config.SCHEDULER_TYPE}_"
                f"{int(config.WORLD_WIDTH)}x{int(config.WORLD_HEIGHT)}_"
                f"mob{config.MOBILE_BUOY_COUNT}_fix{config.FIXED_BUOY_COUNT}.csv"
            )
        filepath = os.path.join(results_dir, filename)

        with open(filepath, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Metric", "Value"])
            for key, value in summary.items():
                writer.writerow([key, value])
        logging.log_info(f"Metrics exported to {filepath}")
