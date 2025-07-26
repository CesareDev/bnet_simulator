from enum import Enum, auto

class EventType(Enum):
    SCHEDULER_CHECK = auto()       # Check if buoy should send a beacon
    CHANNEL_SENSE = auto()         # Check if channel is free
    DIFS_COMPLETION = auto()       # DIFS waiting period completes
    BACKOFF_COMPLETION = auto()    # Backoff period completes
    TRANSMISSION_START = auto()    # Buoy starts transmitting
    TRANSMISSION_END = auto()      # Transmission completes
    RECEPTION = auto()             # Buoy receives a beacon
    NEIGHBOR_CLEANUP = auto()      # Check for expired neighbors
    BUOY_MOVEMENT = auto()         # Update buoy position
    CHANNEL_UPDATE = auto()        # Clean up expired transmissions
    BUOY_ARRAY_UPDATE = auto()     # Update the array of buoys