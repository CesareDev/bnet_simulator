import csv
from bnet_simulator.utils import logging

class Metrics:
    def __init__(self):
        self.beacons_sent = 0
        self.beacons_received = 0
        self.beacons_lost = 0
        self.beacons_collided = 0
        self.total_latency = 0.0  # if you want to compute average delay
        self.discovery_times = {}  # receiver_id -> {sender_id -> first_seen_time}
        self.reaction_latencies = []  # list of all first-contact delays
        self.delivered_beacons = set()  # To avoid counting duplicates

    def log_sent(self):
        self.beacons_sent += 1

    def log_received(self, sender_id, timestamp, receive_time, receiver_id=None):
        key = (sender_id, timestamp)
        if key not in self.delivered_beacons:
            self.beacons_received += 1
            self.delivered_beacons.add(key)
            self.total_latency += receive_time - timestamp

            # Compute reaction latency (first discovery between sender and receiver)
            if receiver_id is not None:
                if receiver_id not in self.discovery_times:
                    self.discovery_times[receiver_id] = {}
                if sender_id not in self.discovery_times[receiver_id]:
                    latency = receive_time - timestamp  # first reception latency
                    self.reaction_latencies.append(latency)
                    self.discovery_times[receiver_id][sender_id] = receive_time

    def log_lost(self):
        self.beacons_lost += 1

    def log_collision(self):
        self.beacons_collided += 1

    def summary(self, sim_time: float):
        avg_latency = self.total_latency / self.beacons_received if self.beacons_received else 0
        return {
            "Sent": self.beacons_sent,
            "Received": self.beacons_received,
            "Lost": self.beacons_lost,
            "Collisions": self.beacons_collided,
            "Avg Latency": avg_latency,
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
    
    def export_metrics_to_csv(self, summary, filename="simulation_metrics.csv"):

        with open(filename, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Header row
            writer.writerow(["Metric", "Value"])

            # Write all metrics
            for key, value in summary.items():
                writer.writerow([key, value])

        logging.log_info(f"Metrics exported to {filename}")