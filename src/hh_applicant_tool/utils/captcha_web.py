"""Local browser prompt for human CAPTCHA entry."""
import base64
import json
import logging
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from threading import Lock, Thread

from ..errors import OperationCanceled

logger = logging.getLogger("hh_applicant_tool")

PAGE = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Ручная проверка HH</title>
<style>
:root { color-scheme: dark; font: 16px system-ui, sans-serif; color: #f0f4ff; background: #101624; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 20px;
  background: radial-gradient(ellipse at top, #29395c, transparent 68%); }
main { width: min(100%, 450px); padding: clamp(20px, 6vw, 34px); background: #192237;
  border: 1px solid #3a4968; border-radius: 24px; box-shadow: 0 24px 64px #080d1a99; }
header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
strong { color: #bdd0fa; font-size: .8rem; letter-spacing: .12em; }
h1 { margin: 20px 0 8px; font-size: clamp(1.55rem, 6vw, 2rem); }
p { margin: 0; color: #becae4; line-height: 1.5; }
figure { margin: 22px 0 16px; padding: 16px; border-radius: 14px; background: #f3f6fc; }
img { display: block; max-width: 100%; margin: auto; color: #172038; }
label { display: grid; gap: 8px; font-weight: 600; }
button, input { font: inherit; color: inherit; background: #273652; border: 1px solid #53678d;
  border-radius: 10px; padding: 10px 12px; }
input { width: 100%; background: #11192a; }
button { cursor: pointer; }
button[type=submit] { width: 100%; margin-top: 12px; background: #b4caff; color: #15213c; font-weight: 700; }
:focus-visible { outline: 2px solid #b4caff; outline-offset: 4px; }
#sound-hint { font-size: .85rem; padding-top: 16px; margin-top: 22px; border-top: 1px solid #3a4968; }
</style>
<main><header><strong>HH / ЛОКАЛЬНО</strong><button id="sound" type="button">Включить звук</button></header>
<h1>Ручная проверка HH</h1><p id="status" role="status">Подключение к CLI…</p>
<form hidden><figure><img alt="Капча HH"></figure>
<label>Символы с картинки <input required maxlength="128" autocomplete="off" spellcheck="false"></label>
<button type="submit">Отправить ответ</button></form>
<p id="sound-hint" role="status">Включите звук один раз, чтобы слышать новые запросы.</p></main>
<script>
const form = document.querySelector('form'), input = form.querySelector('input');
const status = document.querySelector('#status'), url = location.pathname + '/challenge';
let id = null, audio = null, played = null;
const sound = document.querySelector('#sound'), hint = document.querySelector('#sound-hint');
function ring() {
  const now = audio.currentTime;
  for (const [pitch, offset] of [[880, 0], [1320, .12]]) {
    const start = now + offset, note = audio.createOscillator(), volume = audio.createGain();
    note.frequency.value = pitch;
    volume.gain.setValueAtTime(.13, start);
    volume.gain.exponentialRampToValueAtTime(.001, start + .22);
    note.connect(volume).connect(audio.destination);
    note.start(start);
    note.stop(start + .23);
  }
}
function notify() {
  if (id && id !== played && audio?.state === 'running') {
    ring();
    played = id;
  }
}
sound.onclick = async () => {
  try {
    const Audio = window.AudioContext || window.webkitAudioContext;
    audio ??= new Audio();
    await audio.resume();
    if (audio.state !== 'running') throw Error();
    if (id && id !== played) notify();
    else ring();
    sound.textContent = 'Проверить звук';
    hint.textContent = 'Звук включён в этой вкладке.';
  } catch { hint.textContent = 'Звук недоступен. Капча появится без звонка.'; }
};
async function poll() {
  try {
    const response = await fetch(url);
    if (!response.ok) throw Error();
    const {id: next, image} = await response.json();
    if (next !== id) {
      id = next;
      input.value = '';
      form.hidden = !id;
      if (id) {
        form.querySelector('img').src = 'data:image/png;base64,' + image;
        input.focus();
      }
    }
    notify();
    status.textContent = id ? 'Введите текст с картинки.' : 'Ожидание капчи. Не закрывайте вкладку.';
  } catch { status.textContent = 'Нет связи с CLI. Повторяем подключение…'; }
  setTimeout(poll, 1000);
}
form.onsubmit = async event => {
  event.preventDefault();
  const text = input.value.trim(), submitted = id;
  if (!submitted || !text) return;
  try {
    const response = await fetch(url, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: submitted, text})});
    if (!response.ok) throw Error();
    if (id === submitted) {
      form.hidden = true;
      status.textContent = 'Ответ передан.';
    }
  } catch { status.textContent = 'Ответ не отправлен. Проверьте текущую капчу.'; }
};
poll();
</script></html>'''.encode('utf-8')


class CaptchaWebPrompt:
    def __init__(self):
        route = '/' + secrets.token_urlsafe(24)
        lock = Lock()
        self.challenge = None
        self.image_requested = False

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # No challenge URLs or answers in logs.

            def reply(self, status, body=b'', kind='text/plain'):
                self.send_response(status)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers()
                self.wfile.write(body)

            def valid_host(self):
                return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

            def do_GET(handler):
                if not handler.valid_host():
                    return handler.reply(404)
                if handler.path == route:
                    logger.debug("Веб-капча: браузер запросил страницу")
                    return handler.reply(200, PAGE, 'text/html; charset=utf-8')
                if handler.path != route + '/challenge':
                    return handler.reply(404)
                with lock:
                    challenge = self.challenge
                    if challenge is not None and not self.image_requested:
                        self.image_requested = True
                        logger.debug("Веб-капча: браузер запросил изображение")
                body = dict(id=None) if challenge is None else dict(id=challenge[0], image=challenge[1])
                handler.reply(200, json.dumps(body).encode(), 'application/json')

            def do_POST(handler):
                if not handler.valid_host() or handler.path != route + '/challenge':
                    logger.debug("Веб-капча: ответ отклонён, неверный Host или маршрут (404)")
                    return handler.reply(404)
                if handler.headers.get('Origin') != self.origin:
                    logger.debug("Веб-капча: ответ отклонён, неверный Origin (403)")
                    return handler.reply(403)
                try:
                    size = int(handler.headers.get('Content-Length', '0'))
                    if not 0 < size <= 2048 or handler.headers.get_content_type() != 'application/json':
                        logger.debug("Веб-капча: ответ отклонён, неверный размер или Content-Type (400)")
                        return handler.reply(400)
                    handler.connection.settimeout(5)
                    data = json.loads(handler.rfile.read(size))
                    text = data.get('text') if isinstance(data, dict) else None
                    if not isinstance(text, str) or not 0 < len(text.strip()) <= 128 or not text.strip().isprintable():
                        logger.debug("Веб-капча: ответ отклонён, поле text не прошло проверку (400)")
                        return handler.reply(400)
                except (ValueError, OSError) as ex:
                    logger.debug("Веб-капча: ошибка чтения ответа (%s, 400)", type(ex).__name__)
                    return handler.reply(400)
                with lock:
                    challenge = self.challenge
                    if challenge is not None and data.get('id') == challenge[0]:
                        self.challenge = None
                        challenge[2].put_nowait(text.strip())
                    else:
                        challenge = None
                if challenge:
                    logger.debug("Веб-капча: ответ принят локальным сервером (204), проверка HH ещё не выполнена")
                else:
                    logger.debug("Веб-капча: ответ на неактуальное задание (409)")
                handler.reply(204 if challenge else 409)

        self.lock = lock
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.url = self.origin + route
        self.solver = Lock()
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.debug("Веб-капча: локальный сервер запущен на %s", self.origin)

    def prompt(self, image: bytes, *, timeout=180) -> str:
        # ponytail: serialize challenges; one browser tab per CLI process.
        with self.solver:
            answer = Queue(maxsize=1)
            with self.lock:
                self.image_requested = False
                self.challenge = (secrets.token_hex(8), base64.b64encode(image).decode(), answer)
                logger.debug("Веб-капча: изображение доступно браузеру (%d байт), ожидание ввода до %g с", len(image), timeout)
            try:
                text = answer.get(timeout=timeout)
                logger.debug("Веб-капча: ответ передан CLI, длина=%d", len(text))
                return text
            except Empty:
                logger.warning("Веб-капча: истекло время ручного ввода")
                raise OperationCanceled('Истекло время ручного ввода капчи') from None
            finally:
                with self.lock:
                    self.challenge = None
                logger.debug("Веб-капча: задание снято с публикации")

    def open(self):
        print(f'Ручная капча: {self.url}', flush=True)
        try:
            opened = webbrowser.open(self.url)
            logger.debug("Веб-капча: запрос открытия браузера, обработан=%s", opened)
        except (webbrowser.Error, OSError) as ex:
            logger.warning("Веб-капча: браузер не открылся (%s), используйте ссылку из терминала", type(ex).__name__)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        logger.debug("Веб-капча: локальный сервер остановлен")
