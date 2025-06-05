# Beacon settings
NEIGHBOR_TIMEOUT = 10.0  # seconds
BEACON_MIN_INTERVAL = 1.0
BEACON_MAX_INTERVAL = 5.0
BIT_RATE = 1_000_000 # bits per second
SPEED_OF_LIGHT = 3e8  # m/s

# Buoy settings
DEFAULT_BATTERY = 100.0  # %
DEFAULT_BUOY_VELOCITY = 2.0 # m/s
DEFAULT_BOAT_VELOCITY = 20.0 # m/s
COMMUNICATION_RANGE_MAX = 60.0 # Max range for any beacon
COMMUNICATION_RANGE_THRESHOLD = 30.0 # Up to this, 100% delivery
DELIVERY_PROB_OVER_THRESHOLD = 0.7 # Probability if over threshold
NEIGHBOR_TIMEOUT = 5.0  # seconds
DIFS_TIME = 0.048 # seconds
BACKOFF_TIME_MIN = 0.001 # seconds
BACKOFF_TIME_MAX = 0.016 # seconds
SCHEDULER_TYPE = "static"  # Options: "static", "dynamic", "rl"

SAFE_DISTANCE = 10.0  # meters, minimum distance between buoys

# Simulation settings
TARGET_FPS = 60
SIMULATION_DURATION = 120.0  # seconds
ENABLE_METRICS = True  # Set to False to disable metrics collection
SEED = None
HEADLESS = True

# World settings
WORLD_WIDTH = 400.0  # meters or units
WORLD_HEIGHT = 400.0  # meters or units
MOBILE_BUOY_COUNT = 10  # Number of mobile buoys
FIXED_BUOY_COUNT = 10 # Number of fixed buoys

# GUI settings
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
BUOY_RADIUS = 2.0
BG_COLOR = (30, 30, 30)
MOBILE_COLOR = (0, 200, 255)
FIXED_COLOR = (255, 255, 100)
MAX_NEIGHBORS_DISPLAYED = 5
