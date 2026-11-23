"""Run with .venv/bin/python tests/check_captcha_web.py. No HH requests."""
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from time import sleep

import requests

from hh_applicant_tool.errors import OperationCanceled
from hh_applicant_tool.utils.captcha_web import CaptchaWebPrompt

prompt = CaptchaWebPrompt()
url = prompt.url + '/challenge'
try:
    page = requests.get(prompt.url, timeout=2)
    page.raise_for_status()
    assert "Включить звук" in page.text and "AudioContext" in page.text
    assert requests.get(url, timeout=2).json() == {'id': None}
    with ThreadPoolExecutor() as pool:
        result = pool.submit(prompt.prompt, b'fake image', timeout=3)
        for _ in range(100):
            challenge = requests.get(url, timeout=2).json()
            if challenge['id']:
                break
            sleep(.01)
        else:
            raise AssertionError('No active challenge')
        payload = {'id': challenge['id'], 'text': 'answer'}
        assert requests.post(url, json=payload, timeout=2).status_code == 403
        headers = {'Origin': prompt.origin}
        with TestCase().assertLogs('hh_applicant_tool', level='DEBUG') as captured:
            assert requests.post(url, headers=headers, json={**payload, 'id': 'stale'}, timeout=2).status_code == 409
            assert requests.post(url, headers=headers, json=payload, timeout=2).status_code == 204
            assert result.result(2) == 'answer'
        logs = '\n'.join(captured.output)
        assert 'неактуальное задание (409)' in logs
        assert 'проверка HH ещё не выполнена' in logs
        assert prompt.url not in logs and challenge['id'] not in logs and 'answer' not in logs
    try:
        prompt.prompt(b'fake image', timeout=.01)
    except OperationCanceled:
        assert requests.get(url, timeout=2).json() == {'id': None}
    else:
        raise AssertionError('Expected timeout')
finally:
    prompt.close()
