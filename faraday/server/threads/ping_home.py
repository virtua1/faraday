import logging
import threading
import requests
import faraday

logger = logging.getLogger(__name__)

RUN_INTERVAL = 43200
HOME_URL = "https://portal.faradaysec.com/api/v1/license_check"


class PingHomeThread(threading.Thread):
    def __init__(self):
        super().__init__(name="PingHomeThread")
        self.__event = threading.Event()

    def run(self):
        while not self.__event.is_set():
            try:
                res = requests.get(HOME_URL, params={'version': faraday.__version__, 'key': 'white'},
                                   timeout=1, verify=True)
                if res.status_code != 200:
                    logger.error("Invalid response from portal")
                else:
                    logger.debug("Ping Home")
            except Exception as ex:
                logger.exception(ex)
                logger.warning("Can't connect to portal...")
            self.__event.wait(RUN_INTERVAL)

    def stop(self):
        self.__event.set()
