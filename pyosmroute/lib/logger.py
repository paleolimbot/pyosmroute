
import logging

__is_configured = False
DEBUG = "debug"
ERROR = "error"
MESSAGE = "message"


def config_logger(**kwargs):
    if "level" not in kwargs:
        kwargs["level"] = logging.DEBUG
    global __is_configured
    logging.basicConfig(level=logging.DEBUG)
    __is_configured = True


def log(message, level=logging.DEBUG, stacktrace=False):
    if not __is_configured:
        return
    if stacktrace:
        logging.exception(message)
    else:
        logging.log(level, message)