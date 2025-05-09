from bnet_simulator.utils import logging

def main() -> None:
    logging.log_info("Hello from bnet_simulator!")
    logging.log_debug("Debugging information")
    logging.log_warning("This is a warning")
    logging.log_error("An error occurred")
    logging.log_critical("Critical error! Immediate attention needed")

if __name__ == "__main__":
    main()