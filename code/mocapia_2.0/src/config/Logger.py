import logging as log
from typing import Final

LOGGER_HANDLER_PATH :Final[str]= r"config\Settings\log.txt"

class Logger:
    """"""
    _instance = None # Singleton instance

    @staticmethod
    def get_logger():
        if Logger._instance is None:
            Logger._instance = log.getLogger("UserActions")
            Logger._instance.setLevel(log.INFO)

            handler = log.FileHandler(LOGGER_HANDLER_PATH)
            handler.setLevel(log.INFO)

            formater = log.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formater)

            Logger._instance.addHandler(handler)
            Logger._instance.propagate = False # Prevents the log from being printed to the console
        
        return Logger._instance
    
