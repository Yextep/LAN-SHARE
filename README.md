# LAN Share

Servidor web local, simple y sin dependencias externas, para enviar y recibir archivos entre dispositivos conectados a la misma red local.

`LAN Share` nace como una alternativa mas completa a:

```bash
python3 -m http.server
```

El servidor HTTP integrado de Python permite descargar archivos, pero no incluye una interfaz comoda para subir archivos desde otro dispositivo. Este script agrega una interfaz web con subida, descarga, carpetas, ZIP, token opcional y controles basicos de seguridad para uso en LAN.

## Caracteristicas

- Interfaz web responsive para navegador movil o escritorio.
- Descarga de archivos desde la carpeta compartida.
- Subida de uno o varios archivos.
- Arrastrar y soltar archivos en la pagina.
- Subida de carpetas en navegadores compatibles.
- Creacion de carpetas desde la interfaz web.
- Descarga de carpetas como archivo `.zip`.
- Descargas con soporte de rangos HTTP (`Range`), util para reanudar o reproducir archivos grandes.
- Escritura atomica: primero guarda en un archivo temporal y luego reemplaza/mueve al destino final.
- Proteccion contra rutas peligrosas tipo `../`.
- Token opcional para que solo pueda entrar quien tenga el enlace completo.
- Restriccion por defecto a IPs locales, privadas o loopback.
- Sin dependencias de `pip`: usa solo la libreria estandar de Python.

## Requisitos

- Python 3.10 o superior.
- Linux, macOS, Windows, Termux o entorno similar con acceso a red local.
- Dos dispositivos en la misma red, por ejemplo:
  - PC y telefono.
  - Telefono y tablet.
  - PC y otra PC.
  - Maquina virtual y host, si la red esta configurada correctamente.

No necesitas instalar Flask, Django, Node.js ni paquetes externos.

## Instalacion

Clona el repositorio o descarga el script:

```bash
git clone https://github.com/Yextep/LAN-SHARE
cd LAN-SHARE
```

Da permisos de ejecucion:

```bash
chmod +x lan_share.py
```

Tambien puedes ejecutarlo directamente con Python:

```bash
python3 lan_share.py
```

## Uso rapido

Comparte la carpeta actual:

```bash
./lan_share.py
```

Comparte una carpeta concreta:

```bash
./lan_share.py --root ~/Descargas
```

Inicia el servidor con token automatico:

```bash
./lan_share.py --token auto
```

Al arrancar, el script imprimira una o varias URLs:

```text
[+] LAN Share 1.0.0
[+] Carpeta: /home/user/Descargas
[+] Escuchando en: 0.0.0.0:8000
[+] Modo: lectura y escritura
[+] Token activo: usa una de estas URLs completas
[+] URLs:
    http://192.168.1.45:8000/?token=TOKEN_GENERADO
    http://127.0.0.1:8000/?token=TOKEN_GENERADO
```

Abre la URL que empieza por la IP de tu red local, por ejemplo `http://192.168.1.45:8000/...`, desde el otro dispositivo.

## Opciones

```text
usage: lan_share.py [-h] [-r ROOT] [--host HOST] [-p PORT] [--token [TOKEN]]
                    [--max-upload-mb MB] [--overwrite] [--read-only]
                    [--allow-public] [--quiet]
```

| Opcion | Descripcion |
| --- | --- |
| `-r`, `--root ROOT` | Carpeta que se comparte. Por defecto es la carpeta actual. |
| `--host HOST` | IP donde escucha el servidor. Por defecto `0.0.0.0`, acepta conexiones desde la LAN. |
| `-p`, `--port PORT` | Puerto HTTP. Por defecto `8000`. |
| `--token [TOKEN]` | Protege la web con token. Usa `--token auto` para generar uno aleatorio. |
| `--max-upload-mb MB` | Limite maximo por archivo subido. `0` desactiva el limite. |
| `--overwrite` | Sobrescribe archivos existentes. Sin esta opcion, crea nombres como `archivo (1).txt`. |
| `--read-only` | Desactiva subidas y creacion de carpetas. Sirve solo para compartir descargas. |
| `--allow-public` | Permite clientes fuera de rangos privados/locales. No recomendado para uso normal. |
| `--quiet` | Reduce los logs de peticiones HTTP. |

## Ejemplos

### Compartir una carpeta con subida y descarga

```bash
./lan_share.py --root ~/Compartido --token auto
```

### Usar otro puerto

```bash
./lan_share.py --port 9000 --token auto
```

### Modo solo lectura

Util para que otros dispositivos solo descarguen archivos:

```bash
./lan_share.py --root ~/Videos --read-only --token auto
```

### Limitar cada subida a 500 MB

```bash
./lan_share.py --root ~/Recibidos --max-upload-mb 500 --token auto
```

### Sobrescribir archivos existentes

```bash
./lan_share.py --root ~/Recibidos --overwrite --token auto
```

### Escuchar solo en localhost

Util si quieres usar un tunel local o probar sin exponerlo a la LAN:

```bash
./lan_share.py --host 127.0.0.1
```

## Como enviar archivos desde otro dispositivo

1. Ejecuta `LAN Share` en el dispositivo que recibira los archivos.
2. Copia la URL LAN que aparece en la terminal.
3. Abre esa URL en el navegador del otro dispositivo.
4. Usa `Subir archivos`, `Subir carpeta` o arrastra archivos a la zona de subida.
5. Los archivos apareceran dentro de la carpeta compartida.

Si usaste `--token auto`, debes abrir la URL completa con `?token=...`.

## Como descargar archivos desde otro dispositivo

1. Ejecuta el servidor en el dispositivo que tiene los archivos.
2. Abre la URL desde el navegador del otro dispositivo.
3. Pulsa `Bajar` junto al archivo.
4. Para descargar una carpeta completa, pulsa `ZIP`.

## Uso con curl

Aunque esta pensado para navegador, tambien puedes usarlo desde terminal.

Consultar estado:

```bash
curl "http://192.168.1.45:8000/api/status?token=TOKEN"
```

Subir un archivo:

```bash
curl -X POST \
  --data-binary @foto.jpg \
  "http://192.168.1.45:8000/api/upload?dir=&name=foto.jpg&token=TOKEN"
```

Descargar un archivo:

```bash
curl -o foto.jpg \
  "http://192.168.1.45:8000/download?p=foto.jpg&token=TOKEN"
```

Crear una carpeta:

```bash
curl -X POST \
  "http://192.168.1.45:8000/api/mkdir?dir=&name=recibidos&token=TOKEN"
```

Subir dentro de una carpeta:

```bash
curl -X POST \
  --data-binary @documento.pdf \
  "http://192.168.1.45:8000/api/upload?dir=recibidos&name=documento.pdf&token=TOKEN"
```

## Seguridad

Este proyecto esta pensado para redes locales confiables. No esta disenado para exponerse directamente a Internet.

Medidas incluidas:

- Rechazo de rutas fuera de la carpeta compartida.
- Bloqueo de componentes peligrosos como `..`.
- Token opcional por URL o cabecera `X-Share-Token`.
- Acepta por defecto solo clientes con IP privada, local o link-local.
- Escritura atomica para reducir archivos corruptos si se corta la conexion.
- Descargas con cabeceras seguras basicas como `X-Content-Type-Options`.

Recomendaciones:

- Usa siempre `--token auto` si hay mas personas en la red.
- No uses `--allow-public` salvo que entiendas el riesgo.
- No ejecutes el script como `root` si no es necesario.
- Comparte solo una carpeta concreta, no todo tu `$HOME`.
- Deten el servidor con `Ctrl+C` cuando termines.

## Solucion de problemas

### El otro dispositivo no puede abrir la URL

Comprueba que ambos dispositivos esten en la misma red Wi-Fi o LAN.

Verifica la IP del dispositivo que ejecuta el servidor:

```bash
ip addr
```

Tambien puedes probar con otro puerto:

```bash
./lan_share.py --port 9000 --token auto
```

Si hay firewall activo, permite conexiones entrantes al puerto elegido.

### La URL 127.0.0.1 no funciona desde otro dispositivo

`127.0.0.1` siempre apunta al propio dispositivo. Desde otro equipo debes usar la IP LAN, por ejemplo:

```text
http://192.168.1.45:8000/
```

### Aparece "Token requerido"

Abriste la URL sin el token. Usa la URL completa que imprime la terminal:

```text
http://IP:8000/?token=TOKEN
```

### El archivo subido aparece con otro nombre

Por defecto, si el archivo ya existe, el script evita sobrescribirlo y guarda una copia con sufijo:

```text
archivo.txt
archivo (1).txt
archivo (2).txt
```

Para sobrescribir, arranca con:

```bash
./lan_share.py --overwrite --token auto
```

### Quiero solo descargar, no recibir archivos

Usa modo solo lectura:

```bash
./lan_share.py --read-only --token auto
```

## Detalles tecnicos

- Servidor basado en `ThreadingHTTPServer`.
- Interfaz HTML, CSS y JavaScript embebida en el propio script.
- Subidas mediante `POST /api/upload` con `application/octet-stream`.
- Listado mediante `GET /api/list`.
- Descarga mediante `GET /download`.
- Exportacion ZIP mediante `GET /zip`.
- Creacion de carpetas mediante `POST /api/mkdir`.
- Descargas con `Content-Disposition`, `ETag`, `Last-Modified` y `Accept-Ranges`.
- Archivos temporales `.upload-*.part` durante la subida.

## Desarrollo

Comprobar sintaxis:

```bash
python3 -m py_compile lan_share.py
```

Ver opciones:

```bash
./lan_share.py --help
```

Prueba local rapida:

```bash
mkdir -p /tmp/lan-share-test
./lan_share.py --root /tmp/lan-share-test --host 127.0.0.1 --port 8000 --token auto
```

Luego abre la URL `http://127.0.0.1:8000/?token=...` en tu navegador.

## Licencia

Creative Commons Atribución-NoComercial-SinDerivadas 
CC BY-NC-ND 4.0 

