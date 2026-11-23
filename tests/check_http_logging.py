"""Run with .venv/bin/python tests/check_http_logging.py."""
import io
import logging
from unittest.mock import patch

import requests

from hh_applicant_tool.utils.http import LoggedSession

logger = logging.getLogger("hh_applicant_tool")
stream = io.StringIO()
logger.addHandler(logging.StreamHandler(stream))
logger.setLevel(logging.DEBUG)

with LoggedSession() as session:
    with patch.object(requests.Session, "send", return_value=requests.Response()) as send:
        send.return_value.status_code = 204
        session.post("https://example.com/private?key=secret", data="secret")
    with patch.object(requests.Session, "send", side_effect=requests.Timeout("secret")):
        try:
            session.get("https://example.com/private?key=secret")
        except requests.Timeout:
            pass
        else:
            raise AssertionError("Timeout was swallowed")

assert stream.getvalue().splitlines() == [
    "HTTP POST example.com 204",
    "HTTP GET example.com Timeout",
]
