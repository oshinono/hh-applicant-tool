import logging
from urllib.parse import urlsplit

import requests

logger = logging.getLogger("hh_applicant_tool")


class LoggedSession(requests.Session):
    def send(self, request, **kwargs):
        # ponytail: log request metadata only; never headers, query strings or bodies.
        host = urlsplit(request.url).hostname
        try:
            response = super().send(request, **kwargs)
        except requests.RequestException as ex:
            logger.debug("HTTP %s %s %s", request.method, host, type(ex).__name__)
            raise
        logger.debug("HTTP %s %s %s", request.method, host, response.status_code)
        return response
