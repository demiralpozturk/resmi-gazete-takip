"""Statik siteyi derler: docs/ + data/ + RSS → tek klasör (GitHub Pages yükler)."""

from __future__ import annotations

import functools
import hashlib
import http.server
import shutil
from pathlib import Path

from .depo import KOK, VERI


def site_kur(cikti: Path) -> Path:
    cikti = Path(cikti).resolve()
    if cikti == KOK or cikti in KOK.parents or (KOK in cikti.parents and cikti.name in {"docs", "data", "feeds", "rgtakip", "config", "tests"}):
        raise ValueError(f"Çıktı klasörü kaynak klasörlerden biri olamaz: {cikti}")
    if cikti.exists():
        shutil.rmtree(cikti)
    shutil.copytree(KOK / "docs", cikti)
    if VERI.exists():
        shutil.copytree(VERI, cikti / "data", ignore=shutil.ignore_patterns("*.tmp"))
    if (KOK / "feed.xml").exists():
        shutil.copy2(KOK / "feed.xml", cikti / "feed.xml")
    if (KOK / "feeds").exists():
        shutil.copytree(KOK / "feeds", cikti / "feeds")
    (cikti / ".nojekyll").write_text("", encoding="utf-8")
    _onbellek_kir(cikti)
    return cikti


def _onbellek_kir(cikti: Path) -> None:
    """index.html'deki app.js / style.css bağlantılarına içerik özeti ekler (?v=…)."""
    sayfa = cikti / "index.html"
    html = sayfa.read_text(encoding="utf-8")
    for ad in ("style.css", "app.js"):
        ozet = hashlib.sha256((cikti / ad).read_bytes()).hexdigest()[:10]
        html = html.replace(f'"{ad}"', f'"{ad}?v={ozet}"')
    sayfa.write_text(html, encoding="utf-8", newline="\n")


class _Isleyici(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".xml": "application/rss+xml; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
    }


def sun(klasor: Path, port: int) -> None:
    isleyici = functools.partial(_Isleyici, directory=str(klasor))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), isleyici) as sunucu:
        print(f"Site: http://127.0.0.1:{port}/  (durdurmak için Ctrl+C)")
        try:
            sunucu.serve_forever()
        except KeyboardInterrupt:
            pass
