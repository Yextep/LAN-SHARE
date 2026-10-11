"""Create a private persistent signing key and upload it as GitHub Actions secrets.

No credentials are stored in the repository or printed. Keep this key for updates.
"""
import base64
import os
from pathlib import Path
import secrets
import subprocess

directory = Path.home() / ".local/share/brisa-signing"
directory.mkdir(parents=True, exist_ok=True)
directory.chmod(0o700)
key = directory / "brisa.p12"
password_file = directory / "password"
if key.exists() != password_file.exists():
    raise SystemExit("La clave de firma está incompleta. Recupera el respaldo antes de continuar.")
if not key.exists():
    password_file.write_text(secrets.token_urlsafe(36))
    password_file.chmod(0o600)
    env = dict(os.environ, BRISA_KEY_PASSWORD=password_file.read_text())
    subprocess.run(["keytool", "-genkeypair", "-keystore", str(key), "-storetype", "PKCS12",
                    "-alias", "brisa", "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000",
                    "-storepass:env", "BRISA_KEY_PASSWORD", "-keypass:env", "BRISA_KEY_PASSWORD",
                    "-dname", "CN=Brisa, OU=LAN Share, O=Yextep"], env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    key.chmod(0o600)
for name, value in [("BRISA_SIGNING_KEYSTORE", base64.b64encode(key.read_bytes())),
                    ("BRISA_SIGNING_PASSWORD", password_file.read_bytes())]:
    subprocess.run(["gh", "secret", "set", name, "--repo", "Yextep/LAN-SHARE"], input=value,
                   check=True, stdout=subprocess.DEVNULL)
print("Firma de Brisa preparada. La clave privada queda fuera del repositorio.")
