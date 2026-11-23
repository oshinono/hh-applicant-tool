""".venv/bin/python tests/check_ai_rate_limit.py — без сети и ожидания."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from hh_applicant_tool.ai.openai import OpenAIClient, OpenAIError

client = OpenAIClient("http://localhost")
response = Mock(status_code=429, url="http://localhost", request=SimpleNamespace(method="POST"))
response.elapsed.total_seconds.return_value = 0
response.headers = {"Retry-After": "34490"}
with (
    patch.object(client, "_request", return_value=response) as request,
    patch.object(client, "_postpone_requests") as postpone,
):
    with TestCase().assertRaisesRegex(OpenAIError, r"34490 с \(максимум 30 с\)"):
        client.complete("system", "question", model="example")
    request.assert_called_once()
    postpone.assert_not_called()

response.status_code = 200
response.json.return_value = {
    "choices": [{"message": {"content": "sample-result"}}],
    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
}
with (
    patch.object(client, "_request", return_value=response) as request,
    TestCase().assertLogs("hh_applicant_tool", level="DEBUG") as captured,
):
    assert client.recognize_text("system", b"sample-image", model="example") == "sample-result"
    assert "_trace_vision" not in request.call_args.args[0]
logs = "\n".join(captured.output)
assert "Base64" in logs and "попытка 1/" in logs and "разбираю JSON" in logs
assert "вход=4, выход=2" in logs and "sample-result" not in logs
