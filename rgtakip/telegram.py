"""İsteğe bağlı Telegram bildirimi.

TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri yoksa hiçbir şey yapmaz.
TELEGRAM_KATEGORILER: virgülle kategori kodları (ör. "gumruk,dis-ticaret") ya da "hepsi".
Boşsa yalnız vurgulu kategoriler (gümrük + dış ticaret) gönderilir.
"""

from __future__ import annotations

import html
import json
import os
from datetime import date
from pathlib import Path

import requests

from .etiket import Etiketleyici

SINIR = 3800  # Telegram mesaj sınırı 4096; payla birlikte güvenli


def _satir(m: dict) -> str:
    ek = " · ".join(x for x in [m.get("tur_kisa"), m.get("kurum")] if x)
    satir = f'• <a href="{html.escape(m["url"], quote=True)}">{html.escape(m["baslik"], quote=False)}</a>'
    if m.get("mukerrer"):
        ek = (ek + " · " if ek else "") + f"{m['mukerrer']}. Mükerrer"
    if ek:
        satir += f" <i>({html.escape(ek, quote=False)})</i>"
    return satir


def mesajlar(maddeler: list[dict], baslik_eki: str = "") -> list[str]:
    gunler: dict[str, list[dict]] = {}
    for m in maddeler:
        gunler.setdefault(m["tarih"], []).append(m)
    parcalar: list[str] = []
    for tarih in sorted(gunler):
        d = date.fromisoformat(tarih)
        parcalar.append(f"<b>Resmî Gazete — {d:%d.%m.%Y}</b>{baslik_eki}")
        parcalar.extend(_satir(m) for m in gunler[tarih])
        parcalar.append("")
    sonuc: list[str] = []
    tampon = ""
    for p in parcalar:
        if len(tampon) + len(p) + 1 > SINIR and tampon:
            sonuc.append(tampon.rstrip())
            tampon = ""
        tampon += p + "\n"
    if tampon.strip():
        sonuc.append(tampon.rstrip())
    return sonuc


def secilenler(maddeler: list[dict], etiketleyici: Etiketleyici, ayar: str | None) -> list[dict]:
    ayar = (ayar or "").strip()
    if ayar.lower() == "hepsi":
        return maddeler
    istenen = {k.strip() for k in ayar.split(",") if k.strip()} or set(etiketleyici.vurgulu_kodlar())
    return [m for m in maddeler if istenen & set(m.get("kategoriler", []))]


def gonder(yeni_dosya: Path, etiketleyici: Etiketleyici) -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    sohbet = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not sohbet:
        print("Telegram ayarı yok (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID); bildirim atlandı.")
        return 0
    maddeler = json.loads(Path(yeni_dosya).read_text(encoding="utf-8"))["maddeler"] if Path(yeni_dosya).exists() else []
    secili = secilenler(maddeler, etiketleyici, os.environ.get("TELEGRAM_KATEGORILER"))
    if not secili:
        print("Bildirilecek yeni madde yok.")
        return 0
    for metin in mesajlar(secili):
        yanit = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": sohbet, "text": metin, "parse_mode": "HTML", "disable_web_page_preview": "true"},
            timeout=30,
        )
        if not yanit.ok:
            # Belirteci günlüğe yazma; yalnız durum kodunu ve Telegram'ın açıklamasını göster
            aciklama = yanit.json().get("description", "") if yanit.headers.get("content-type", "").startswith("application/json") else ""
            print(f"Telegram hatası: HTTP {yanit.status_code} {aciklama}")
            return 1
    print(f"Telegram: {len(secili)} madde gönderildi.")
    return 0
