
import logging

__is_configured = False
DEBUG = "debug"
ERROR = "error"
MESSAGE = "message"


def config_logger(**kwargs):
    """
    Configure the logging and start logging messages from this package. Defaults to
    logging level=logging.DEBUG

    :param kwargs: Passed to logging.basicConfig()
    """
    if "level" not in kwargs:
        kwargs["level"] = logging.DEBUG
    global __is_configured
    logging.basicConfig(**kwargs)
    __is_configured = True


def log(message, level=logging.DEBUG, stacktrace=False):
    """
    Log a message from this package.

    :param message: The message
    :param level: the logging level to use
    :param stacktrace: Print a stacktrace of the last exception.
    """
    if not __is_configured:
        return
    if stacktrace:
        logging.exception(message)
    else:
        logging.log(level, message)