#!/usr/bin/env python3
"""
LAN Share: small, dependency-free file sender/receiver for trusted local networks.

It serves a web file manager with downloads, uploads, folder upload, atomic writes,
range downloads, zip export, optional token auth, and local-network client checks.
"""

from __future__ import annotations

import argparse
import contextlib
import email.utils
import html
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any


APP_NAME = "LAN Share"
VERSION = "1.0.0"
CHUNK_SIZE = 1024 * 1024


class RequestError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class LANShareServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    root: Path
    token: str
    max_upload_bytes: int
    overwrite: bool
    read_only: bool
    allow_public: bool
    quiet: bool
    write_lock: threading.Lock


HTML_PAGE = r"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LAN Share</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --surface: #ffffff;
      --surface-2: #eef3f2;
      --text: #1d252c;
      --muted: #60707a;
      --line: #d9e0e4;
      --accent: #16756f;
      --accent-2: #9a6b00;
      --danger: #a43b3b;
      --shadow: 0 8px 24px rgba(18, 31, 37, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 64px;
      padding: 0 24px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .brand {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    .brand strong {
      font-size: 17px;
      font-weight: 700;
    }
    .brand span,
    .status-line {
      color: var(--muted);
      font-size: 13px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    button,
    .button {
      appearance: none;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      text-decoration: none;
    }
    button:hover,
    .button:hover {
      border-color: #aab7bd;
      background: #fafafa;
    }
    .primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }
    .primary:hover {
      background: #12645f;
      border-color: #12645f;
    }
    .crumbs {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      min-height: 40px;
      margin-bottom: 12px;
      color: var(--muted);
    }
    .crumbs button {
      min-height: 32px;
      padding: 0 9px;
      background: transparent;
    }
    .dropzone {
      border: 1px dashed #9eb0b5;
      background: var(--surface-2);
      min-height: 96px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      margin-bottom: 16px;
      padding: 18px;
      transition: border-color 0.15s ease, background 0.15s ease;
    }
    .dropzone strong {
      display: block;
      font-size: 16px;
      margin-bottom: 3px;
    }
    .dropzone span {
      color: var(--muted);
      font-size: 13px;
    }
    .dropzone.active {
      border-color: var(--accent);
      background: #e2f0ee;
    }
    .table-wrap,
    .transfers {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th,
    td {
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: middle;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      background: #fbfcfc;
    }
    tr:last-child td { border-bottom: 0; }
    .name { width: 54%; }
    .size { width: 14%; }
    .mtime { width: 20%; }
    .file-actions { width: 12%; text-align: right; }
    .entry-name {
      border: 0;
      background: transparent;
      color: var(--text);
      padding: 0;
      min-height: 0;
      justify-content: flex-start;
      max-width: 100%;
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .entry-name:hover {
      background: transparent;
      color: var(--accent);
    }
    .muted { color: var(--muted); }
    .empty {
      padding: 44px 16px;
      text-align: center;
      color: var(--muted);
    }
    .transfers {
      margin-top: 16px;
      display: none;
    }
    .transfers.visible { display: block; }
    .transfer-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 120px;
      gap: 12px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }
    .transfer-row:last-child { border-bottom: 0; }
    .transfer-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 600;
    }
    .bar {
      height: 7px;
      border-radius: 999px;
      background: #dfe7e8;
      overflow: hidden;
      margin-top: 7px;
    }
    .bar span {
      display: block;
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width 0.12s linear;
    }
    .transfer-state {
      text-align: right;
      color: var(--muted);
      font-size: 13px;
    }
    .transfer-row.failed .bar span { background: var(--danger); width: 100%; }
    .transfer-row.done .bar span { background: var(--accent-2); width: 100%; }
    input[type="file"] { display: none; }
    @media (max-width: 740px) {
      header {
        align-items: flex-start;
        flex-direction: column;
        justify-content: center;
        padding: 12px 16px;
      }
      main { padding: 14px; }
      .toolbar {
        align-items: stretch;
        flex-direction: column;
      }
      .actions button,
      .actions .button { flex: 1 1 145px; }
      .size,
      .mtime { display: none; }
      .name { width: 70%; }
      .file-actions { width: 30%; }
      th,
      td { padding: 10px 9px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <strong>LAN Share</strong>
      <span id="rootLabel">Cargando...</span>
    </div>
    <div class="status-line" id="statusLine">Listo</div>
  </header>
  <main>
    <div class="toolbar">
      <div class="actions" id="writeActions">
        <button class="primary" id="pickFiles" type="button">Subir archivos</button>
        <button id="pickFolder" type="button">Subir carpeta</button>
        <button id="newFolder" type="button">Nueva carpeta</button>
        <button id="refresh" type="button">Actualizar</button>
      </div>
      <a class="button" id="zipLink" href="#">Descargar carpeta</a>
    </div>
    <nav class="crumbs" id="crumbs"></nav>
    <section class="dropzone" id="dropzone">
      <div>
        <strong>Suelta archivos aqui</strong>
        <span>Tambien acepta carpetas en navegadores compatibles</span>
      </div>
    </section>
    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="name">Nombre</th>
            <th class="size">Tamano</th>
            <th class="mtime">Modificado</th>
            <th class="file-actions"></th>
          </tr>
        </thead>
        <tbody id="listing">
          <tr><td colspan="4" class="empty">Cargando...</td></tr>
        </tbody>
      </table>
    </section>
    <section class="transfers" id="transfers"></section>
    <input id="fileInput" type="file" multiple>
    <input id="folderInput" type="file" multiple webkitdirectory directory>
  </main>
  <script>
    const config = __CONFIG__;
    const paramsAtLoad = new URLSearchParams(location.search);
    const token = paramsAtLoad.get('token') || '';
    const state = { path: normalizePath(paramsAtLoad.get('p') || '') };

    const els = {
      rootLabel: document.getElementById('rootLabel'),
      statusLine: document.getElementById('statusLine'),
      writeActions: document.getElementById('writeActions'),
      crumbs: document.getElementById('crumbs'),
      listing: document.getElementById('listing'),
      dropzone: document.getElementById('dropzone'),
      transfers: document.getElementById('transfers'),
      fileInput: document.getElementById('fileInput'),
      folderInput: document.getElementById('folderInput'),
      pickFiles: document.getElementById('pickFiles'),
      pickFolder: document.getElementById('pickFolder'),
      newFolder: document.getElementById('newFolder'),
      refresh: document.getElementById('refresh'),
      zipLink: document.getElementById('zipLink')
    };

    if (config.readOnly) {
      els.writeActions.style.display = 'none';
      els.dropzone.style.display = 'none';
    }

    function normalizePath(value) {
      return String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    }

    function urlFor(path, params) {
      const query = new URLSearchParams(params || {});
      if (token) query.set('token', token);
      const qs = query.toString();
      return qs ? `${path}?${qs}` : path;
    }

    function setStatus(text) {
      els.statusLine.textContent = text;
    }

    function formatBytes(bytes) {
      if (bytes === null || bytes === undefined) return '';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let value = Number(bytes);
      let unit = 0;
      while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
      }
      const precision = unit === 0 || value >= 10 ? 0 : 1;
      return `${value.toFixed(precision)} ${units[unit]}`;
    }

    function formatTime(epoch) {
      if (!epoch) return '';
      return new Date(epoch * 1000).toLocaleString();
    }

    function setBrowserPath(path, replace) {
      state.path = normalizePath(path);
      const query = new URLSearchParams();
      if (state.path) query.set('p', state.path);
      if (token) query.set('token', token);
      const next = `${location.pathname}${query.toString() ? '?' + query.toString() : ''}`;
      if (replace) history.replaceState({ path: state.path }, '', next);
      else history.pushState({ path: state.path }, '', next);
    }

    function openPath(path) {
      setBrowserPath(path, false);
      loadListing();
    }

    function renderCrumbs(path) {
      els.crumbs.textContent = '';
      const root = document.createElement('button');
      root.type = 'button';
      root.textContent = 'Inicio';
      root.addEventListener('click', () => openPath(''));
      els.crumbs.appendChild(root);

      const parts = normalizePath(path).split('/').filter(Boolean);
      let acc = '';
      for (const part of parts) {
        const sep = document.createElement('span');
        sep.textContent = '/';
        els.crumbs.appendChild(sep);
        acc = acc ? `${acc}/${part}` : part;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = part;
        btn.title = acc;
        btn.addEventListener('click', () => openPath(btn.title));
        els.crumbs.appendChild(btn);
      }
    }

    function renderListing(data) {
      els.rootLabel.textContent = data.path ? `/${data.path}` : config.rootName;
      els.zipLink.href = urlFor('/zip', { p: data.path || '' });
      renderCrumbs(data.path || '');
      els.listing.textContent = '';

      if (!data.entries.length) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 4;
        td.className = 'empty';
        td.textContent = 'Esta carpeta esta vacia';
        tr.appendChild(td);
        els.listing.appendChild(tr);
        return;
      }

      for (const entry of data.entries) {
        const tr = document.createElement('tr');
        const name = document.createElement('td');
        name.className = 'name';
        const action = document.createElement('button');
        action.type = 'button';
        action.className = 'entry-name';
        action.textContent = `${entry.type === 'dir' ? '[DIR] ' : ''}${entry.name}`;
        action.title = entry.name;
        if (entry.type === 'dir') {
          action.addEventListener('click', () => openPath(entry.path));
        } else {
          action.addEventListener('click', () => {
            location.href = urlFor('/download', { p: entry.path });
          });
        }
        name.appendChild(action);

        const size = document.createElement('td');
        size.className = 'size muted';
        size.textContent = entry.type === 'dir' ? '' : formatBytes(entry.size);

        const mtime = document.createElement('td');
        mtime.className = 'mtime muted';
        mtime.textContent = formatTime(entry.mtime);

        const actions = document.createElement('td');
        actions.className = 'file-actions';
        if (entry.type === 'dir') {
          const link = document.createElement('a');
          link.className = 'button';
          link.href = urlFor('/zip', { p: entry.path });
          link.textContent = 'ZIP';
          actions.appendChild(link);
        } else {
          const link = document.createElement('a');
          link.className = 'button';
          link.href = urlFor('/download', { p: entry.path });
          link.textContent = 'Bajar';
          actions.appendChild(link);
        }

        tr.append(name, size, mtime, actions);
        els.listing.appendChild(tr);
      }
    }

    async function loadListing() {
      setStatus('Leyendo carpeta...');
      try {
        const res = await fetch(urlFor('/api/list', { p: state.path }), { cache: 'no-store' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        renderListing(data);
        setStatus('Listo');
      } catch (err) {
        els.listing.innerHTML = `<tr><td colspan="4" class="empty">${escapeHtml(err.message)}</td></tr>`;
        setStatus('Error');
      }
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[ch]));
    }

    function addTransfer(name, size) {
      els.transfers.classList.add('visible');
      const row = document.createElement('div');
      row.className = 'transfer-row';
      row.innerHTML = `
        <div>
          <div class="transfer-title"></div>
          <div class="bar"><span></span></div>
        </div>
        <div class="transfer-state"></div>`;
      row.querySelector('.transfer-title').textContent = name;
      const stateEl = row.querySelector('.transfer-state');
      const bar = row.querySelector('.bar span');
      stateEl.textContent = formatBytes(size);
      els.transfers.prepend(row);
      return {
        progress(percent) {
          bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
          stateEl.textContent = `${Math.round(percent)}%`;
        },
        done(saved) {
          row.classList.add('done');
          bar.style.width = '100%';
          stateEl.textContent = saved ? 'Guardado' : 'OK';
        },
        failed(message) {
          row.classList.add('failed');
          stateEl.textContent = message || 'Fallo';
        }
      };
    }

    function uploadOne(item) {
      return new Promise(resolve => {
        const file = item.file;
        const relativePath = normalizePath(item.relativePath || file.name);
        const progress = addTransfer(relativePath, file.size);
        const xhr = new XMLHttpRequest();
        xhr.open('POST', urlFor('/api/upload', { dir: state.path, name: relativePath }));
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');
        xhr.setRequestHeader('X-File-Mtime', String(file.lastModified ? file.lastModified / 1000 : ''));
        xhr.upload.onprogress = event => {
          if (event.lengthComputable) progress.progress((event.loaded / event.total) * 100);
        };
        xhr.onload = () => {
          let payload = {};
          try { payload = JSON.parse(xhr.responseText || '{}'); } catch (_) {}
          if (xhr.status >= 200 && xhr.status < 300) {
            progress.done(payload.saved);
          } else {
            progress.failed(payload.error || `HTTP ${xhr.status}`);
          }
          resolve();
        };
        xhr.onerror = () => {
          progress.failed('Red');
          resolve();
        };
        xhr.send(file);
      });
    }

    async function startUploads(items) {
      if (config.readOnly || !items.length) return;
      const queue = items.slice();
      const workers = [];
      const concurrency = Math.min(3, queue.length);
      setStatus(`Subiendo ${queue.length} archivo(s)...`);
      async function worker() {
        while (queue.length) {
          const next = queue.shift();
          await uploadOne(next);
        }
      }
      for (let i = 0; i < concurrency; i++) workers.push(worker());
      await Promise.all(workers);
      await loadListing();
    }

    function filesFromInput(input) {
      return Array.from(input.files || []).map(file => ({
        file,
        relativePath: file.webkitRelativePath || file.name
      }));
    }

    function readAllDirectoryEntries(reader) {
      return new Promise((resolve, reject) => {
        const entries = [];
        function readBatch() {
          reader.readEntries(batch => {
            if (!batch.length) resolve(entries);
            else {
              entries.push(...batch);
              readBatch();
            }
          }, reject);
        }
        readBatch();
      });
    }

    function fileFromEntry(entry, relativePath) {
      return new Promise((resolve, reject) => {
        entry.file(file => resolve({ file, relativePath: `${relativePath}${file.name}` }), reject);
      });
    }

    async function walkEntry(entry, relativePath, out) {
      if (entry.isFile) {
        out.push(await fileFromEntry(entry, relativePath));
        return;
      }
      if (!entry.isDirectory) return;
      const entries = await readAllDirectoryEntries(entry.createReader());
      const nextPath = `${relativePath}${entry.name}/`;
      for (const child of entries) {
        await walkEntry(child, nextPath, out);
      }
    }

    async function filesFromDrop(dataTransfer) {
      const items = Array.from(dataTransfer.items || []);
      if (items.length && items.some(item => item.webkitGetAsEntry)) {
        const out = [];
        for (const item of items) {
          const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
          if (entry) await walkEntry(entry, '', out);
        }
        if (out.length) return out;
      }
      return Array.from(dataTransfer.files || []).map(file => ({ file, relativePath: file.name }));
    }

    async function createFolder() {
      const raw = prompt('Nombre de la carpeta');
      const name = normalizePath(raw || '');
      if (!name) return;
      setStatus('Creando carpeta...');
      try {
        const res = await fetch(urlFor('/api/mkdir', { dir: state.path, name }), { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        await loadListing();
      } catch (err) {
        setStatus(err.message);
      }
    }

    els.pickFiles.addEventListener('click', () => els.fileInput.click());
    els.pickFolder.addEventListener('click', () => els.folderInput.click());
    els.newFolder.addEventListener('click', createFolder);
    els.refresh.addEventListener('click', loadListing);
    els.fileInput.addEventListener('change', async () => {
      await startUploads(filesFromInput(els.fileInput));
      els.fileInput.value = '';
    });
    els.folderInput.addEventListener('change', async () => {
      await startUploads(filesFromInput(els.folderInput));
      els.folderInput.value = '';
    });

    for (const eventName of ['dragenter', 'dragover']) {
      els.dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        els.dropzone.classList.add('active');
      });
    }
    for (const eventName of ['dragleave', 'drop']) {
      els.dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        els.dropzone.classList.remove('active');
      });
    }
    els.dropzone.addEventListener('drop', async event => {
      await startUploads(await filesFromDrop(event.dataTransfer));
    });
    window.addEventListener('popstate', event => {
      state.path = normalizePath((event.state && event.state.path) || new URLSearchParams(location.search).get('p') || '');
      loadListing();
    });

    setBrowserPath(state.path, true);
    loadListing();
  </script>
</body>
</html>
"""


AUTH_PAGE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Token requerido</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f6f7f9;
      color: #1d252c;
      font: 15px/1.45 system-ui, sans-serif;
    }
    main {
      width: min(440px, calc(100vw - 32px));
      background: #fff;
      border: 1px solid #d9e0e4;
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 8px 24px rgba(18, 31, 37, 0.08);
    }
    h1 { font-size: 20px; margin: 0 0 8px; }
    p { color: #60707a; margin: 0; }
  </style>
</head>
<body>
  <main>
    <h1>Token requerido</h1>
    <p>Abre la URL completa que aparece en la terminal del servidor.</p>
  </main>
</body>
</html>
"""


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def is_within(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def safe_parts(value: str, *, allow_empty: bool = True) -> list[str]:
    value = (value or "").replace("\\", "/").strip("/")
    if not value:
        if allow_empty:
            return []
        raise RequestError(400, "Nombre vacio")

    pure = PurePosixPath(value)
    if pure.is_absolute():
        raise RequestError(400, "Ruta absoluta no permitida")

    parts = [part for part in pure.parts if part not in ("", ".")]
    if not parts and not allow_empty:
        raise RequestError(400, "Nombre vacio")

    for part in parts:
        if part == ".." or "\x00" in part:
            raise RequestError(400, "Ruta no permitida")
        if len(part.encode("utf-8", "ignore")) > 255:
            raise RequestError(400, "Un nombre es demasiado largo")
    return parts


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(1, 10000):
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    raise RequestError(409, "No se pudo generar un nombre unico")


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "download"
    quoted = urllib.parse.quote(filename, safe="")
    return f'{disposition}; filename="{fallback}"; filename*=UTF-8\'\'{quoted}'


def parse_range_header(value: str, total: int) -> tuple[int, int]:
    if not value.startswith("bytes=") or "," in value:
        raise RequestError(416, "Rango no soportado")
    spec = value[6:].strip()
    if "-" not in spec:
        raise RequestError(416, "Rango invalido")
    first, last = spec.split("-", 1)
    try:
        if first == "":
            suffix = int(last)
            if suffix <= 0:
                raise ValueError
            start = max(total - suffix, 0)
            end = total - 1
        else:
            start = int(first)
            end = int(last) if last else total - 1
    except ValueError as exc:
        raise RequestError(416, "Rango invalido") from exc

    if total == 0 or start < 0 or start >= total or end < start:
        raise RequestError(416, "Rango fuera del archivo")
    return start, min(end, total - 1)


def parse_client_ip(value: str) -> ipaddress._BaseAddress | None:
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return None
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped or ip


def is_local_network_ip(value: str) -> bool:
    ip = parse_client_ip(value)
    if ip is None:
        return False
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local)


class LANShareHandler(BaseHTTPRequestHandler):
    server_version = f"LANShare/{VERSION}"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_HEAD(self) -> None:
        self.dispatch("HEAD")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def dispatch(self, method: str) -> None:
        self.parsed_url = urllib.parse.urlsplit(self.path)
        self.query = urllib.parse.parse_qs(self.parsed_url.query, keep_blank_values=True)
        try:
            if not self.server.allow_public and not is_local_network_ip(self.client_address[0]):
                raise RequestError(403, "Cliente fuera de la red local")
            if not self.is_authorized():
                self.send_auth_required(method == "HEAD")
                return

            path = self.parsed_url.path
            if method in ("GET", "HEAD") and path == "/":
                self.handle_index(method == "HEAD")
            elif method in ("GET", "HEAD") and path == "/api/list":
                self.handle_list(method == "HEAD")
            elif method in ("GET", "HEAD") and path == "/api/status":
                self.handle_status(method == "HEAD")
            elif method in ("GET", "HEAD") and path == "/download":
                self.handle_download(method == "HEAD")
            elif method in ("GET", "HEAD") and path == "/zip":
                self.handle_zip(method == "HEAD")
            elif method == "POST" and path == "/api/upload":
                self.handle_upload()
            elif method == "POST" and path == "/api/mkdir":
                self.handle_mkdir()
            elif method in ("GET", "HEAD") and path == "/favicon.ico":
                self.respond(b"", 204, "image/x-icon", head=method == "HEAD")
            else:
                raise RequestError(404, "Ruta no encontrada")
        except RequestError as exc:
            self.respond_error(exc.status, exc.message, head=method == "HEAD")
        except BrokenPipeError:
            return
        except ConnectionResetError:
            return
        except Exception as exc:  # noqa: BLE001 - keep server alive for every request.
            if not self.server.quiet:
                print(f"[!] Error inesperado: {exc}", file=sys.stderr)
            self.respond_error(500, "Error interno", head=method == "HEAD")

    def is_authorized(self) -> bool:
        expected = self.server.token
        if not expected:
            return True
        candidates = []
        candidates.extend(self.query.get("token", []))
        header = self.headers.get("X-Share-Token")
        if header:
            candidates.append(header)
        return any(secrets.compare_digest(candidate, expected) for candidate in candidates)

    def send_auth_required(self, head: bool = False) -> None:
        if self.parsed_url.path.startswith("/api/"):
            self.respond_json({"error": "Token requerido"}, 401, head=head)
        else:
            self.respond(AUTH_PAGE.encode("utf-8"), 401, "text/html; charset=utf-8", head=head)

    def get_query_value(self, name: str, default: str = "") -> str:
        values = self.query.get(name)
        if not values:
            return default
        return values[0]

    def resolve_path(self, value: str, *, must_exist: bool = True) -> Path:
        parts = safe_parts(value, allow_empty=True)
        target = self.server.root.joinpath(*parts).resolve(strict=False)
        if not is_within(self.server.root, target):
            raise RequestError(403, "Ruta fuera de la carpeta compartida")
        if must_exist and not target.exists():
            raise RequestError(404, "No existe")
        return target

    def relative_path(self, target: Path) -> str:
        rel = target.relative_to(self.server.root)
        return "" if str(rel) == "." else rel.as_posix()

    def respond(
        self,
        body: bytes,
        status: int = 200,
        content_type: str = "application/octet-stream",
        *,
        headers: dict[str, str] | None = None,
        head: bool = False,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'",
            )
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if not head and body:
            self.wfile.write(body)

    def respond_json(self, payload: Any, status: int = 200, *, head: bool = False) -> None:
        self.respond(json_bytes(payload), status, "application/json; charset=utf-8", head=head)

    def respond_error(self, status: int, message: str, *, head: bool = False) -> None:
        if self.parsed_url.path.startswith("/api/"):
            self.respond_json({"error": message}, status, head=head)
            return
        body = f"{status} {html.escape(message)}\n".encode("utf-8")
        self.respond(body, status, "text/plain; charset=utf-8", head=head)

    def handle_index(self, head: bool) -> None:
        config = {
            "rootName": self.server.root.name or str(self.server.root),
            "readOnly": self.server.read_only,
            "maxUploadBytes": self.server.max_upload_bytes,
        }
        config_json = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
        body = HTML_PAGE.replace("__CONFIG__", config_json).encode("utf-8")
        self.respond(body, 200, "text/html; charset=utf-8", headers={"Cache-Control": "no-store"}, head=head)

    def handle_status(self, head: bool) -> None:
        self.respond_json(
            {
                "app": APP_NAME,
                "version": VERSION,
                "root": str(self.server.root),
                "readOnly": self.server.read_only,
                "overwrite": self.server.overwrite,
                "maxUploadBytes": self.server.max_upload_bytes,
            },
            head=head,
        )

    def handle_list(self, head: bool) -> None:
        target = self.resolve_path(self.get_query_value("p"))
        if not target.is_dir():
            raise RequestError(400, "La ruta no es una carpeta")

        entries: list[dict[str, Any]] = []
        for child in target.iterdir():
            try:
                resolved = child.resolve(strict=True)
                if not is_within(self.server.root, resolved):
                    continue
                stat = child.stat()
                is_dir = child.is_dir()
            except OSError:
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": self.relative_path(child),
                    "type": "dir" if is_dir else "file",
                    "size": None if is_dir else stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )

        entries.sort(key=lambda item: (item["type"] != "dir", item["name"].casefold()))
        rel = self.relative_path(target)
        parent = ""
        if rel:
            parent_path = PurePosixPath(rel).parent
            parent = "" if str(parent_path) == "." else parent_path.as_posix()
        self.respond_json({"path": rel, "parent": parent, "entries": entries}, head=head)

    def handle_mkdir(self) -> None:
        if self.server.read_only:
            raise RequestError(403, "Servidor en modo solo lectura")
        base = self.resolve_path(self.get_query_value("dir"))
        if not base.is_dir():
            raise RequestError(400, "Destino no es carpeta")
        name = self.get_query_value("name")
        parts = safe_parts(name, allow_empty=False)
        target = base.joinpath(*parts).resolve(strict=False)
        if not is_within(self.server.root, target):
            raise RequestError(403, "Ruta fuera de la carpeta compartida")
        if target.exists():
            raise RequestError(409, "Ya existe")
        target.mkdir(parents=True, exist_ok=False)
        self.respond_json({"ok": True, "path": self.relative_path(target)}, 201)

    def handle_upload(self) -> None:
        if self.server.read_only:
            raise RequestError(403, "Servidor en modo solo lectura")

        length_header = self.headers.get("Content-Length")
        if not length_header:
            raise RequestError(411, "Content-Length requerido")
        try:
            length = int(length_header)
        except ValueError as exc:
            raise RequestError(400, "Content-Length invalido") from exc
        if length < 0:
            raise RequestError(400, "Content-Length invalido")
        if self.server.max_upload_bytes and length > self.server.max_upload_bytes:
            raise RequestError(413, "Archivo supera el limite configurado")

        base = self.resolve_path(self.get_query_value("dir"))
        if not base.is_dir():
            raise RequestError(400, "Destino no es carpeta")

        parts = safe_parts(self.get_query_value("name"), allow_empty=False)
        target = base.joinpath(*parts).resolve(strict=False)
        if not is_within(self.server.root, target):
            raise RequestError(403, "Ruta fuera de la carpeta compartida")
        if target.exists() and target.is_dir():
            raise RequestError(409, "Ya existe una carpeta con ese nombre")

        target.parent.mkdir(parents=True, exist_ok=True)
        parent_resolved = target.parent.resolve(strict=True)
        if not is_within(self.server.root, parent_resolved):
            raise RequestError(403, "Ruta fuera de la carpeta compartida")

        fd, tmp_name = tempfile.mkstemp(prefix=".upload-", suffix=".part", dir=str(parent_resolved))
        tmp_path = Path(tmp_name)
        try:
            remaining = length
            with os.fdopen(fd, "wb") as handle:
                while remaining:
                    chunk = self.rfile.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise RequestError(400, "Conexion cerrada durante la subida")
                    handle.write(chunk)
                    remaining -= len(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            final_path = target
            with self.server.write_lock:
                if not self.server.overwrite:
                    final_path = unique_destination(target)
                elif final_path.exists() and final_path.is_dir():
                    raise RequestError(409, "Ya existe una carpeta con ese nombre")
                os.replace(tmp_path, final_path)

            mtime_header = self.headers.get("X-File-Mtime", "").strip()
            with contextlib.suppress(ValueError, OSError):
                if mtime_header:
                    mtime = float(mtime_header)
                    os.utime(final_path, (time.time(), mtime))

            self.respond_json(
                {
                    "ok": True,
                    "saved": self.relative_path(final_path),
                    "size": final_path.stat().st_size,
                },
                201,
            )
        finally:
            with contextlib.suppress(FileNotFoundError):
                tmp_path.unlink()

    def handle_download(self, head: bool) -> None:
        target = self.resolve_path(self.get_query_value("p"))
        if not target.is_file():
            raise RequestError(400, "La ruta no es un archivo")
        self.send_file(target, target.name, head=head)

    def handle_zip(self, head: bool) -> None:
        target = self.resolve_path(self.get_query_value("p"))
        name = (target.name or self.server.root.name or "share") + ".zip"

        tmp = tempfile.NamedTemporaryFile(prefix="lan-share-", suffix=".zip", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            self.build_zip(target, tmp_path)
            self.send_file(tmp_path, name, head=head, remove_after=True)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                tmp_path.unlink()
            raise

    def build_zip(self, target: Path, output: Path) -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            if target.is_file():
                archive.write(target, arcname=target.name)
                return

            root_name = target.name or self.server.root.name or "share"
            for current, dirs, files in os.walk(target, followlinks=False):
                current_path = Path(current)
                safe_dirs = []
                for dirname in dirs:
                    candidate = current_path / dirname
                    with contextlib.suppress(OSError):
                        if is_within(self.server.root, candidate.resolve(strict=True)):
                            safe_dirs.append(dirname)
                dirs[:] = safe_dirs

                for filename in files:
                    file_path = current_path / filename
                    try:
                        if file_path.is_symlink():
                            continue
                        resolved = file_path.resolve(strict=True)
                        if not is_within(self.server.root, resolved):
                            continue
                    except OSError:
                        continue
                    rel = file_path.relative_to(target)
                    archive.write(file_path, arcname=str(PurePosixPath(root_name) / PurePosixPath(rel.as_posix())))

    def send_file(self, path: Path, download_name: str, *, head: bool = False, remove_after: bool = False) -> None:
        try:
            stat = path.stat()
            total = stat.st_size
            content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
            start = 0
            end = total - 1
            status = 200
            range_header = self.headers.get("Range")
            headers = {
                "Content-Disposition": content_disposition(download_name),
                "Accept-Ranges": "bytes",
                "Last-Modified": email.utils.formatdate(stat.st_mtime, usegmt=True),
                "ETag": f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"',
            }
            if range_header:
                start, end = parse_range_header(range_header, total)
                status = 206
                headers["Content-Range"] = f"bytes {start}-{end}/{total}"
            length = 0 if total == 0 else end - start + 1

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

            if not head and length:
                with path.open("rb") as handle:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        chunk = handle.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
        finally:
            if remove_after:
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()

    def log_message(self, fmt: str, *args: Any) -> None:
        if self.server.quiet:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        message = fmt % args
        print(f"[{timestamp}] {self.client_address[0]} {message}", file=sys.stderr)


def discover_lan_ips(bind_host: str) -> list[str]:
    if bind_host not in ("", "0.0.0.0", "::"):
        return [bind_host]

    found: set[str] = {"127.0.0.1"}
    hostname = socket.gethostname()
    with contextlib.suppress(OSError):
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_DGRAM):
            ip = info[4][0]
            if is_local_network_ip(ip):
                found.add(ip)

    for target in ("8.8.8.8", "1.1.1.1"):
        with contextlib.suppress(OSError):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect((target, 80))
                ip = sock.getsockname()[0]
                if is_local_network_ip(ip):
                    found.add(ip)
            finally:
                sock.close()

    return sorted(found, key=lambda value: (value.startswith("127."), value))


def make_url(host: str, port: int, token: str) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    query = urllib.parse.urlencode({"token": token}) if token else ""
    return f"http://{display_host}:{port}/" + (f"?{query}" if query else "")


def human_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    precision = 0 if unit == 0 or value >= 10 else 1
    return f"{value:.{precision}f} {units[unit]}"


def positive_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("puerto invalido") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("puerto fuera de rango")
    return port


def upload_limit(value: str) -> int:
    try:
        mb = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limite invalido") from exc
    if mb < 0:
        raise argparse.ArgumentTypeError("limite negativo")
    return int(mb * 1024 * 1024)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Servidor web local para enviar y recibir archivos en una LAN.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-r", "--root", default=".", help="carpeta que se comparte")
    parser.add_argument("--host", default="0.0.0.0", help="IP donde escucha el servidor")
    parser.add_argument("-p", "--port", type=positive_port, default=8000, help="puerto HTTP")
    parser.add_argument(
        "--token",
        nargs="?",
        const="auto",
        default="",
        help="protege la web con token; usa '--token' o '--token auto' para generar uno",
    )
    parser.add_argument(
        "--max-upload-mb",
        type=upload_limit,
        default=0,
        metavar="MB",
        help="limite por archivo subido; 0 desactiva el limite",
    )
    parser.add_argument("--overwrite", action="store_true", help="sobrescribe archivos existentes")
    parser.add_argument("--read-only", action="store_true", help="desactiva subidas y creacion de carpetas")
    parser.add_argument(
        "--allow-public",
        action="store_true",
        help="acepta clientes con IP no privada; no recomendado fuera de pruebas controladas",
    )
    parser.add_argument("--quiet", action="store_true", help="reduce logs de peticiones")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"[x] La carpeta no existe: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"[x] No es una carpeta: {root}", file=sys.stderr)
        return 2

    token = args.token
    if token == "auto":
        token = secrets.token_urlsafe(18)

    server = LANShareServer((args.host, args.port), LANShareHandler)
    server.root = root
    server.token = token
    server.max_upload_bytes = args.max_upload_mb
    server.overwrite = bool(args.overwrite)
    server.read_only = bool(args.read_only)
    server.allow_public = bool(args.allow_public)
    server.quiet = bool(args.quiet)
    server.write_lock = threading.Lock()

    actual_port = server.server_address[1]
    urls = [make_url(ip, actual_port, token) for ip in discover_lan_ips(args.host)]

    print(f"[+] {APP_NAME} {VERSION}")
    print(f"[+] Carpeta: {root}")
    print(f"[+] Escuchando en: {args.host}:{actual_port}")
    print(f"[+] Modo: {'solo lectura' if args.read_only else 'lectura y escritura'}")
    if args.max_upload_mb:
        print(f"[+] Limite por subida: {human_bytes(args.max_upload_mb)}")
    if token:
        print("[+] Token activo: usa una de estas URLs completas")
    else:
        print("[!] Sin token. Se aceptan solo IPs privadas/locales; usa --token auto para proteger el enlace.")
    if args.allow_public:
        print("[!] --allow-public activo: se aceptaran clientes fuera de rangos privados.")
    print("[+] URLs:")
    for url in urls:
        print(f"    {url}")
    print("[+] Ctrl+C para detener.")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[+] Deteniendo servidor.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
