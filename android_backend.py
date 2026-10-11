"""Android adapter. The original LAN Share protocol remains the file engine."""
from __future__ import annotations

import contextlib
import ipaddress
import json
import secrets
import threading
from pathlib import Path

import lan_share as core

_server = None
_lock = threading.RLock()
PAGE = Path(__file__).with_name("brisa.html").read_text(encoding="utf-8")


class BrisaHandler(core.LANShareHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(120)

    def is_authorized(self):
        # A separate, never-shared token protects Android's privileged local UI.
        local = ipaddress.ip_address(self.client_address[0]).is_loopback
        tokens = self.query.get("token", []) + [self.headers.get("X-Share-Token", "")]
        if local and any(secrets.compare_digest(t, self.server.local_token) for t in tokens):
            return True
        return self.server.sharing and super().is_authorized()

    def handle_index(self, head):
        config = {"rootName": "Brisa", "readOnly": self.server.read_only,
                  "maxUploadBytes": self.server.max_upload_bytes}
        body = PAGE.replace("__CONFIG__", json.dumps(config)).encode("utf-8")
        self.respond(body, content_type="text/html; charset=utf-8",
                     headers={"Cache-Control": "no-store"}, head=head)

    def handle_status(self, head):
        self.respond_json({"app": "Brisa", "version": "1.0.0",
                           "readOnly": self.server.read_only,
                           "maxUploadBytes": self.server.max_upload_bytes}, head=head)

    def respond(self, body, status=200, content_type="application/octet-stream", *, headers=None, head=False):
        if status >= 400:
            # A rejected upload may have an unread body: don't reuse that socket.
            self.close_connection = True
            headers = dict(headers or {}, Connection="close")
        return super().respond(body, status, content_type, headers=headers, head=head)

    def resolve_path(self, value, **kwargs):
        if any(p.startswith(".upload-") for p in core.safe_parts(value)):
            raise core.RequestError(403, "Archivo temporal no disponible")
        return super().resolve_path(value, **kwargs)


def start(root):
    global _server
    with _lock:
        if _server is None:
            path = Path(root).resolve()
            path.mkdir(parents=True, exist_ok=True)
            for partial in path.rglob(".upload-*.part"):
                with contextlib.suppress(OSError):
                    partial.unlink()
            server = core.LANShareServer(("0.0.0.0", 0), BrisaHandler)
            server.root = path
            server.token = secrets.token_urlsafe(24)
            server.local_token = secrets.token_urlsafe(32)
            server.sharing = False
            server.read_only = False
            server.overwrite = False
            server.max_upload_bytes = 2 * 1024 ** 3
            server.allow_public = False
            server.quiet = True
            server.write_lock = threading.Lock()
            _server = server
            threading.Thread(target=server.serve_forever, daemon=True).start()
        return core.make_url("127.0.0.1", _server.server_port, _server.local_token)


def state():
    with _lock:
        return json.dumps({"sharing": bool(_server and _server.sharing),
                           "port": _server.server_port if _server else 0,
                           "token": _server.token if _server and _server.sharing else ""})


def set_sharing(enabled):
    with _lock:
        if _server:
            if enabled and not _server.sharing:
                _server.token = secrets.token_urlsafe(24)
            _server.sharing = bool(enabled)
    return state()


def set_read_only(enabled):
    with _lock:
        _server.read_only = bool(enabled)


def import_file(source, name, directory=""):
    """Commit a staged SAF copy, atomically and without overwriting existing files."""
    parts = core.safe_parts(directory)
    filename = core.safe_parts(name, allow_empty=False)
    if len(filename) != 1 or filename[0].startswith(".upload-"):
        raise ValueError("Nombre de archivo no válido")
    target_dir = _server.root.joinpath(*parts).resolve()
    if not core.is_within(_server.root, target_dir) or not target_dir.is_dir():
        raise ValueError("Carpeta no válida")
    # Staging is inside the private shared filesystem: replace stays atomic.
    with _server.write_lock:
        target = core.unique_destination(target_dir / filename[0])
        Path(source).replace(target)
    return target.name


def stop():
    global _server
    with _lock:
        server, _server = _server, None
    if server:
        server.sharing = False
        server.shutdown()
        server.server_close()
