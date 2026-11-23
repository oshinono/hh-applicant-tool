class Error(Exception):
    pass


# Используй эту ошибку для прерывания выполнения команд
class OperationError(Error):
    pass


class OperationCanceled(OperationError):
    pass


class XHRError(Error):
    pass


class CaptchaError(XHRError):
    def __init__(self, captcha_state: str, http_status: int | None = None):
        self.state = captcha_state
        self.http_status = http_status
        super().__init__("Captcha required")


class ReCaptchaError(XHRError):
    def __init__(self, captcha_key: str):
        self.key = captcha_key
        super().__init__("RECAPTCHA required")
