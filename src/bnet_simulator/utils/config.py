# Beacon settings
NEIGHBOR_TIMEOUT = 10.0  # seconds
BEACON_MIN_INTERVAL = 1.0
BEACON_MAX_INTERVAL = 10.0
BEACON_LOSS_PROB = 0.05
TRASMISSION_TIME = 0.1  # seconds

# Buoy settings
DEFAULT_BATTERY = 100.0  # %
DEFAULT_VELOCITY = (0.0, 0.0)
COMMUNICATION_RANGE_MAX = 60.0  # meters or units
COMMUNICATION_RANGE_MIN = 50.0  # meters or units
NEIGHBOR_TIMEOUT = 5.0  # seconds
DEFAULT_VELOCITY = 2.0 # m/s
DIFS_TIME = 0.048

# Simulation settings
TARGET_FPS = 60
SIMULATION_DURATION = 60.0  # seconds
ENABLE_METRICS = False  # Set to False to disable metrics collection

# World settings
WORLD_WIDTH = 200.0  # meters or units
WORLD_HEIGHT = 200.0  # meters or units

# GUI settings
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
BUOY_RADIUS = 5.0
BG_COLOR = (30, 30, 30)
MOBILE_COLOR = (0, 200, 255)
FIXED_COLOR = (255, 255, 100)
MAX_NEIGHBORS_DISPLAYED = 5