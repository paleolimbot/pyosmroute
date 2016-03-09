
import logging

__is_configured = False
DEBUG = "debug"
ERROR = "error"
MESSAGE = "message"


def config_logger():
    global __is_configured
    logging.basicConfig(level=logging.DEBUG)
    __is_configured = True


def log(message, level=DEBUG, stacktrace=False):
    if not __is_configured:
        config_logger()
    if stacktrace:
        logging.exception(message)
    else:
        logging.debug(message)