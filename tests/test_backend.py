"""Exercise the real HTTP server, including its Android session boundary."""
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import android_backend as backend


class BrisaProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.local_url = backend.start(self.root)
        self.base = self.local_url.split("/?")[0]
        self.local_token = urllib.parse.parse_qs(urllib.parse.urlsplit(self.local_url).query)["token"][0]

    def tearDown(self):
        backend.stop()
        self.temporary.cleanup()

    def call(self, route, params=None, body=None, token=None, headers=None):
        query = dict(params or {}, token=token or self.local_token)
        request = urllib.request.Request(self.base + route + "?" + urllib.parse.urlencode(query), data=body, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as response:
            return response.code, response.read(), dict(response.headers)

    def test_guest_requires_active_session_and_previous_link_expires(self):
        first = backend._server.token
        self.assertEqual(self.call("/api/list", token=first)[0], 401)
        backend.set_sharing(True)
        second = backend._server.token
        self.assertNotEqual(first, second)
        self.assertEqual(self.call("/api/list", token=second)[0], 200)
        backend.set_sharing(False)
        self.assertEqual(self.call("/api/list", token=second)[0], 401)
        self.assertEqual(self.call("/api/list")[0], 200)
        backend.set_sharing(True)
        self.assertEqual(self.call("/api/list", token=second)[0], 401)

    def test_upload_duplicate_and_range_preserve_bytes(self):
        payload = bytes(range(256)) * 200
        self.assertEqual(self.call("/api/upload", {"name": "foto á.bin"}, payload)[0], 201)
        self.assertEqual(self.call("/api/upload", {"name": "foto á.bin"}, b"second")[0], 201)
        listing = json.loads(self.call("/api/list")[1])
        self.assertEqual(len(listing["entries"]), 2)
        self.assertTrue((self.root / "foto á (1).bin").exists())
        status, content, headers = self.call("/download", {"p": "foto á.bin"}, headers={"Range": "bytes=100-200"})
        self.assertEqual(status, 206)
        self.assertEqual(content, payload[100:201])
        self.assertEqual(headers["Content-Range"], f"bytes 100-200/{len(payload)}")
        self.assertEqual(self.call("/download", {"p": "foto á.bin"})[1], payload)
        self.assertEqual(self.call("/download", {"p": "foto á.bin"}, headers={"Range": "bytes=999999-"})[0], 416)

    def test_folders_zip_and_private_partial_files(self):
        self.assertEqual(self.call("/api/mkdir", {"name": "Fotos"}, b"")[0], 201)
        self.call("/api/upload", {"dir": "Fotos", "name": "uno.txt"}, b"hola")
        (self.root / "Fotos/.upload-incomplete.part").write_text("secret")
        listing = json.loads(self.call("/api/list", {"p": "Fotos"})[1])
        self.assertEqual([e["name"] for e in listing["entries"]], ["uno.txt"])
        self.assertEqual(self.call("/download", {"p": "Fotos/.upload-incomplete.part"})[0], 403)
        archive = zipfile.ZipFile(io.BytesIO(self.call("/zip", {"p": "Fotos"})[1]))
        self.assertEqual(archive.namelist(), ["Fotos/uno.txt"])
        self.assertEqual(archive.read("Fotos/uno.txt"), b"hola")

    def test_traversal_symlinks_and_readonly(self):
        self.assertEqual(self.call("/api/upload", {"name": "../outside"}, b"bad")[0], 400)
        self.assertEqual(self.call("/api/list", {"p": "../"})[0], 400)
        (self.root / "outside").symlink_to(self.root.parent)
        self.assertEqual(self.call("/api/list", {"p": "outside"})[0], 403)
        backend.set_read_only(True)
        self.assertEqual(self.call("/api/upload", {"name": "blocked"}, b"bad")[0], 403)
        self.assertEqual(self.call("/api/mkdir", {"name": "blocked"}, b"")[0], 403)

    def test_oversize_upload_empty_files_and_staged_atomic_import(self):
        backend._server.max_upload_bytes = 10
        self.assertEqual(self.call("/api/upload", {"name": "large"}, b"x" * 11)[0], 413)
        self.assertFalse((self.root / "large").exists())
        self.assertEqual(self.call("/api/upload", {"name": "empty"}, b"")[0], 201)
        self.assertEqual(self.call("/download", {"p": "empty"})[1], b"")
        source = self.root / ".upload-test.part"
        source.write_bytes(b"correct")
        self.assertEqual(backend.import_file(source, "copiado.txt"), "copiado.txt")
        self.assertFalse(source.exists())
        self.assertEqual((self.root / "copiado.txt").read_bytes(), b"correct")

    def test_html_is_offline_and_handles_hostile_filenames(self):
        self.call("/api/upload", {"name": '<img onerror="bad">.txt'}, b"safe")
        status, html, headers = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn(b"De aqu", html)
        self.assertNotIn(b"__CONFIG__", html)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("token", json.loads(self.call("/api/status")[1]))

    def test_native_delete_cannot_escape_root_and_guests_cannot_delete(self):
        self.call("/api/upload", {"name": "remove.txt"}, b"test")
        backend.set_sharing(True)
        self.assertEqual(self.call("/api/delete", {"p": "remove.txt"}, b"", token=backend._server.token)[0], 404)
        self.assertTrue((self.root / "remove.txt").exists())
        backend.delete_path("remove.txt")
        self.assertFalse((self.root / "remove.txt").exists())
        with self.assertRaises(Exception):
            backend.delete_path("../")
        with self.assertRaises(Exception):
            backend.delete_path("")


if __name__ == "__main__":
    unittest.main()
