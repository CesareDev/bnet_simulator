import sys
from datetime import datetime
from pathlib import Path

COLORS = {
    'INFO': '\033[92m',     # Green
    'DEBUG': '\033[94m',    # Blue
    'WARNING': '\033[93m',  # Yellow
    'ERROR': '\033[91m',    # Red
    'CRITICAL': '\033[95m', # Magenta
    'RESET': '\033[0m',
}

# Default log file path, root of the project
LOG_FILE = Path("simulator.log")

def _log(level: str, message: str, to_console: bool = True, to_file: bool = False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = COLORS.get(level, '')
    reset = COLORS['RESET']
    
    formatted = f"[{timestamp}] [{level}] {message}"

    # Print to console with color
    output = f"{color}{formatted}{reset}"
    if to_console:
        print(output, file=sys.stderr if level in ["ERROR", "CRITICAL"] else sys.stdout)

    # Optionally write to file
    if to_file:
        with LOG_FILE.open("a") as f:
            f.write(formatted + "\n")

def log_info(msg: str, to_console: bool = True, to_file: bool = False): _log("INFO", msg, to_console, to_file)
def log_debug(msg: str, to_console: bool = True, to_file: bool = False): _log("DEBUG", msg, to_console, to_file)
def log_warning(msg: str, to_console: bool = True, to_file: bool = False): _log("WARNING", msg, to_console, to_file)
def log_error(msg: str, to_console: bool = True, to_file: bool = False): _log("ERROR", msg, to_console, to_file)
def log_critical(msg: str, to_console: bool = True, to_file: bool = False): _log("CRITICAL", msg, to_console, to_file)