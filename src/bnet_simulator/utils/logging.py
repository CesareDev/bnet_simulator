def log_info(message: str, level: str = "INFO") -> None:
    """
    Log a message with a specified log level.

    Args:
        message (str): The message to log.
        level (str): The log level. Can be "INFO", "WARNING", "ERROR", or "DEBUG". Defaults to "INFO".
    """
    levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
    if level not in levels:
        raise ValueError(f"Invalid log level: {level}. Must be one of {levels}.")

    print(f"[{level}] {message}")