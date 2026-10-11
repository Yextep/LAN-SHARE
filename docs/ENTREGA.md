# Brisa 1.0 — entrega verificada

- APK: [Brisa.apk](https://github.com/Yextep/LAN-SHARE/releases/download/brisa-v1.0.0/Brisa.apk).
- Release: [Brisa 1.0](https://github.com/Yextep/LAN-SHARE/releases/tag/brisa-v1.0.0).
- Compilación y pruebas: [GitHub Actions 38150776985](https://github.com/Yextep/LAN-SHARE/actions/runs/38150776985), completada correctamente el 11 de octubre de 2026.
- Fuente compilada: `b29a3059683ff32de86bbf7f31fd6c088af39e45`.
- Paquete: `com.brisa.app`, versión `1.0.0`, Android mínimo 7.0 / API 24.
- Arquitecturas: `arm64-v8a`, `armeabi-v7a`, `x86_64`.
- Tamaño exacto: 43 400 499 bytes.
- SHA-256 del APK: `6c57a6faa0254f046283f99a79ebdd650551db60f4db226d9ff0a121477b6db0`.
- Certificado de firma SHA-256: `fb61c8aa5fe7b0854f22c572ff85e25a188c7fc2bb0124de8a8d8e4bed95dde2`.

La firma APK v2 y v3 fue verificada nuevamente después de descargar el artefacto. La interfaz dentro del APK coincide byte a byte con `brisa.html`.

Las siete pruebas del protocolo HTTP pasan: autenticación y caducidad de sesión, subidas, nombres duplicados, descargas por rango, archivos vacíos, carpetas, ZIP, bloqueo de rutas peligrosas, solo descargas y gestión de copias locales.

Las pruebas con Chromium verifican envío y descarga desde la interfaz, carpetas, búsqueda, nombres que contienen HTML, temas, invitados y ausencia de desbordamiento en anchos de 320, 390, 768 y 1200 píxeles.

La prueba de integración en un emulador Android 15 verifica subidas reales mediante WebView, lectura de bytes descargados, guardado mediante ContentResolver, preferencias del tema fuera de localStorage y apertura y cierre del servicio de primer plano. El resultado tiene cero fallos y cero errores. Android Lint tiene cero errores.

Capturas de Android: [modo oscuro](https://github.com/Yextep/LAN-SHARE/releases/download/brisa-v1.0.0/brisa-android-oscuro.png) y [modo claro](https://github.com/Yextep/LAN-SHARE/releases/download/brisa-v1.0.0/brisa-android-claro.png).

Uso y detalles de almacenamiento: [README de Android](../android/README.md).
