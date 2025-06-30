import os
import csv
from bnet_simulator.utils import logging, config

class Metrics:
    def __init__(self, density=None):
        self.beacons_sent = 0
        self.beacons_received = 0
        self.beacons_lost = 0
        self.beacons_collided = 0
        self.total_latency = 0.0
        self.discovery_times = {}
        self.reaction_latencies = []
        self.delivered_beacons = set()
        self.scheduler_latencies = []
        self.potentially_sent = 0  # Total "sent" (sum over all senders × receivers in range)
        self.actually_received = 0  # Total "received" (sum over all receivers)
        self.potentially_sent_per_sender = {}  # sender_id -> count
        self.actually_received_per_sender = {}  # sender_id -> count
        self.density = density
        
        # Vessel-specific tracking
        self.vessel_id = None
        self.potentially_sent_to_vessel = {}  # sender_id -> count of beacons potentially received by vessel
        self.vessel_received_count = 0  # Total beacons received by vessel

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
                    
                    # Track vessel reception
                    if self.vessel_id and receiver_id == self.vessel_id:
                        self.vessel_received_count += 1

    def log_lost(self):
        self.beacons_lost += 1

    def log_collision(self):
        self.beacons_collided += 1

    def record_scheduler_latency(self, latency: float):
        self.scheduler_latencies.append(latency)

    def avg_scheduler_latency(self) -> float:
        return sum(self.scheduler_latencies) / len(self.scheduler_latencies) if self.scheduler_latencies else 0.0
    
    def get_parameters(self) -> dict:
        if config.SCHEDULER_TYPE != "dynamic":
            return {}

        return {
            "Motion Weight": config.MOTION_WEIGHT,
            "Density Weight": config.DENSITY_WEIGHT,
            "Contact Weight": config.CONTACT_WEIGHT,
            "Congestion Weight": config.CONGESTION_WEIGHT,
            "Density Midpoint": config.DENSITY_MIDPOINT,
            "Density Alpha": config.DENSITY_ALPHA,
            "Contact Midpoint": config.CONTACT_MIDPOINT,
            "Contact Alpha": config.CONTACT_ALPHA,
        }

    def log_potentially_sent(self, sender_id, n_receivers):
        self.potentially_sent += n_receivers
        self.potentially_sent_per_sender[sender_id] = self.potentially_sent_per_sender.get(sender_id, 0) + n_receivers

    def log_actually_received(self, sender_id):
        self.actually_received += 1
        self.actually_received_per_sender[sender_id] = self.actually_received_per_sender.get(sender_id, 0) + 1

    def delivery_ratio(self):
        return self.actually_received / self.potentially_sent if self.potentially_sent else 0

    def log_vessel_targeted(self, sender_id):
        """Track when a beacon is sent to the vessel (vessel in range)"""
        if self.vessel_id:  # Only track if we have a vessel
            self.potentially_sent_to_vessel[sender_id] = self.potentially_sent_to_vessel.get(sender_id, 0) + 1

    def log_vessel_received(self, sender_id):
        """Track when the vessel successfully receives a beacon"""
        if self.vessel_id:  # Only track if we have a vessel
            self.vessel_received_count += 1

    def vessel_delivery_ratio(self):
        """Calculate delivery ratio specifically for the vessel"""
        if not self.vessel_id or sum(self.potentially_sent_to_vessel.values()) == 0:
            return 0
        
        return self.vessel_received_count / sum(self.potentially_sent_to_vessel.values())

    def summary(self, sim_time: float):
        avg_latency = self.total_latency / self.beacons_received if self.beacons_received else 0
        base_summary = {
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
            "Avg Scheduler Latency": self.avg_scheduler_latency(),
            "Delivery Ratio": self.delivery_ratio(),
            "Collision Rate": self.beacons_collided / self.beacons_sent if self.beacons_sent else 0,
            "Avg Reaction Latency": (
                sum(self.reaction_latencies) / len(self.reaction_latencies)
                if self.reaction_latencies else 0
            ),
            "Throughput (beacons/sec)": (
                self.beacons_received / sim_time
                if sim_time > 0 else 0
            ),
            "Potentially Sent": self.potentially_sent,
            "Actually Received": self.actually_received,
        }
        
        # Add vessel-specific metrics if we have a vessel
        if self.vessel_id:
            base_summary["Is Vessel Scenario"] = True
            base_summary["Vessel ID"] = str(self.vessel_id)
            
            # Calculate vessel-specific metrics
            discovered = 0
            if self.vessel_id in self.discovery_times:
                discovered = len(self.discovery_times[self.vessel_id])
                
            total_potential = sum(self.potentially_sent_to_vessel.values())
            
            base_summary["Vessel Discovered Senders"] = discovered
            base_summary["Vessel Potential Senders"] = len(self.potentially_sent_to_vessel)
            base_summary["Vessel Potential Beacons"] = total_potential
            base_summary["Vessel Received Beacons"] = self.vessel_received_count
            base_summary["Vessel Delivery Ratio"] = self.vessel_delivery_ratio()
            
            # Add per-sender delivery ratios to vessel
            if self.vessel_id in self.discovery_times:
                for sender_id in self.potentially_sent_to_vessel:
                    received = 1 if sender_id in self.discovery_times[self.vessel_id] else 0
                    sent = self.potentially_sent_to_vessel[sender_id]
                    if sent > 0:
                        sender_key = f"Sender {str(sender_id)[:6]} DR to Vessel"
                        base_summary[sender_key] = received / sent
        
        parameters = self.get_parameters()
        summary = {**base_summary, **parameters}
        if self.density is not None:
            summary["Density"] = self.density
        return summary

    def export_metrics_to_csv(self, summary, filename=None):
        if filename is None:
            # Default: save to metrics/tune_results/
            results_dir = os.path.join("metrics", "tune_results")
            os.makedirs(results_dir, exist_ok=True)
            filename = (
                f"{config.SCHEDULER_TYPE}_"
                f"{int(config.WORLD_WIDTH)}x{int(config.WORLD_HEIGHT)}_"
                f"mob{config.MOBILE_BUOY_COUNT}_fix{config.FIXED_BUOY_COUNT}.csv"
            )
            filepath = os.path.join(results_dir, filename)
        else:
            filepath = filename
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Metric", "Value"])
            for key, value in summary.items():
                writer.writerow([key, value])
        logging.log_info(f"Metrics exported to {filepath}")
