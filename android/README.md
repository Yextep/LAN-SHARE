# Brisa para Android

Brisa convierte LAN Share de Yextep en una app autónoma: Python está incluido en el APK y el teléfono sirve los archivos a otros dispositivos de la red. No requiere Termux, una PC, cuentas ni servicios de nube.

## Uso

1. Instala `Brisa.apk` en Android 7.0 o posterior. Si Android lo pide, permite instalar aplicaciones desde el navegador o gestor de archivos que estés usando.
2. Abre Brisa y toca **Añadir archivos**. Se copian a la carpeta privada de la app; los originales permanecen en su lugar.
3. Conecta ambos dispositivos al mismo Wi-Fi o punto de acceso y toca **Empezar a compartir**.
4. Envía el enlace completo o muestra el código QR. El otro dispositivo lo abre en su navegador para descargar o subir archivos. No necesita instalar Brisa.
5. Para guardar un archivo recibido fuera de Brisa, toca su botón de descarga y elige el destino con el selector de Android.
6. Toca **Dejar de compartir** o **Detener** en la notificación para cerrar el acceso desde la red.

También puedes usar **Conectar** para abrir un enlace de LAN Share en el navegador de Android.

Los modos oscuro y claro están en Ajustes y se conservan al volver a abrir. Hay búsqueda, carpetas, ZIP, progreso de subidas, nombres sin sobrescritura, enlaces por sesión y modo solo descargas. Las transferencias locales usan HTTP; utiliza una red de confianza. El tamaño máximo es 2 GB por archivo y depende del espacio libre del teléfono.

El servicio de primer plano mantiene la sesión al salir de la pantalla. Android 15 limita los servicios `dataSync` en segundo plano a seis horas acumuladas; Brisa detiene el servicio correctamente cuando Android lo solicita. El sistema o el fabricante pueden cerrar la app en condiciones de batería extrema. Vuelve a abrirla y crea una sesión nueva si ocurre.

Los archivos dentro de Brisa se conservan al actualizar el APK con la misma firma. Desinstalar o borrar los datos de la app elimina esa carpeta: guarda los archivos que quieras conservar usando el botón de descarga.

## Compilar y verificar

Requiere Java 17, Python 3.11 y SDK Android 35.

```bash
python -m unittest discover -s tests -v
python -m pip install playwright==1.55.0
python -m playwright install chromium
python scripts/browser_smoke.py
cd android
./gradlew assembleRelease assembleDebugAndroidTest lintRelease
```

La fuente Python se incluye directamente desde la raíz del repositorio, sin copias divergentes. El APK admite ARM de 32 y 64 bits y x86 de 64 bits. El puente JavaScript solo se utiliza en la página local con una clave separada que nunca se comparte con invitados. Las descargas se guardan mediante el selector de Android sin pedir acceso general al almacenamiento.

El workflow `.github/workflows/brisa-apk.yml` ejecuta pruebas HTTP, pruebas de interfaz con Chromium y pruebas reales con un emulador Android 15. Solo publica el artefacto firmado si pasan. `scripts/setup_signing.py` prepara una clave persistente fuera del repositorio y los secretos `BRISA_SIGNING_KEYSTORE` y `BRISA_SIGNING_PASSWORD` en GitHub. Conserva una copia privada de la clave y su contraseña para futuras actualizaciones.

Se mantiene la autoría y licencia originales en `LICENSE.md`.
