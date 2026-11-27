"""RSS 2.0 akışları: feed.xml (tümü) ve feeds/<kategori>.xml.

Çıktı belirlenimcidir (lastBuildDate en yeni maddenin tarihidir), böylece
yeni madde yoksa dosyalar değişmez ve commit oluşmaz.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .depo import KOK, yaz_degistiyse
from .etiket import Etiketleyici

TR = timezone(timedelta(hours=3))
ANA_SINIR = 200
KATEGORI_SINIR = 100
VURGULU_KOD = "gumruk-dis-ticaret"


def site_adresi() -> str:
    """Yayın adresi: RG_SITE_URL > GitHub deposundan türetilen Pages adresi > varsayılan."""
    adres = os.environ.get("RG_SITE_URL")
    if adres:
        return adres.rstrip("/") + "/"
    depo = os.environ.get("GITHUB_REPOSITORY")
    if depo and "/" in depo:
        sahip, ad = depo.split("/", 1)
        return f"https://{sahip.lower()}.github.io/{ad}/"
    return "https://demiralpozturk.github.io/resmi-gazete-takip/"


def _sirali(gunler: list[dict]) -> list[dict]:
    """Yeniden eskiye; aynı günde mükerrer sayılar önce, sonra fihrist sırası."""
    sonuc: list[dict] = []
    for g in sorted(gunler, key=lambda g: g["tarih"], reverse=True):
        sonuc.extend(sorted(g["maddeler"], key=lambda m: (-m.get("mukerrer", 0), m.get("sira", 0))))
    return sonuc


def _tarih(madde: dict) -> str:
    d = date.fromisoformat(madde["tarih"])
    return format_datetime(datetime(d.year, d.month, d.day, tzinfo=TR))


def _aciklama(madde: dict, kategori_adlari: dict[str, str]) -> str:
    parcalar = [madde.get("tur_kisa") or ""]
    if madde.get("kurum"):
        parcalar.append(madde["kurum"])
    sayi = f"Sayı {madde['sayi']}" if madde.get("sayi") else ""
    if madde.get("mukerrer"):
        sayi += f" ({madde['mukerrer']}. Mükerrer)"
    if sayi:
        parcalar.append(sayi)
    kategoriler = [kategori_adlari.get(k, k) for k in madde.get("kategoriler", [])]
    if kategoriler:
        parcalar.append("Kategoriler: " + ", ".join(kategoriler))
    return " · ".join(p for p in parcalar if p)


def rss_metni(maddeler: list[dict], baslik: str, aciklama: str, kendi_adresi: str, kategori_adlari: dict[str, str]) -> str:
    site = site_adresi()
    son = _tarih(maddeler[0]) if maddeler else format_datetime(datetime(2026, 1, 1, tzinfo=TR))
    satirlar = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{escape(baslik)}</title>",
        f"<link>{escape(site)}</link>",
        f"<description>{escape(aciklama)}</description>",
        "<language>tr</language>",
        f"<lastBuildDate>{son}</lastBuildDate>",
        f'<atom:link href="{escape(kendi_adresi)}" rel="self" type="application/rss+xml"/>',
        "<generator>resmi-gazete-takip</generator>",
    ]
    for m in maddeler:
        satirlar += [
            "<item>",
            f"<title>{escape(m['baslik'])}</title>",
            f"<link>{escape(m['url'])}</link>",
            f'<guid isPermaLink="false">rg-{escape(m["id"])}</guid>',
            f"<pubDate>{_tarih(m)}</pubDate>",
            f"<description>{escape(_aciklama(m, kategori_adlari))}</description>",
        ]
        satirlar += [f"<category>{escape(kategori_adlari.get(k, k))}</category>" for k in m.get("kategoriler", [])]
        satirlar.append("</item>")
    satirlar += ["</channel>", "</rss>", ""]
    return "\n".join(satirlar)


def akislari_yaz(gunler: list[dict], etiketleyici: Etiketleyici, kok: Path = KOK) -> list[Path]:
    site = site_adresi()
    adlar = {k.kod: k.ad for k in etiketleyici.kategoriler}
    tumu = _sirali(gunler)
    degisen: list[Path] = []

    def yaz(yol: Path, metin: str) -> None:
        if yaz_degistiyse(yol, metin):
            degisen.append(yol)

    yaz(
        kok / "feed.xml",
        rss_metni(
            tumu[:ANA_SINIR],
            "Resmî Gazete — Tüm maddeler",
            "Resmî Gazete'nin günlük fihristi (resmî olmayan, otomatik akış).",
            site + "feed.xml",
            adlar,
        ),
    )
    vurgulu = set(etiketleyici.vurgulu_kodlar())
    if vurgulu:
        secili = [m for m in tumu if vurgulu & set(m.get("kategoriler", []))]
        yaz(
            kok / "feeds" / f"{VURGULU_KOD}.xml",
            rss_metni(
                secili[:KATEGORI_SINIR],
                "Resmî Gazete — Gümrük ve Dış Ticaret",
                "Gümrük, ithalat ve ihracatla ilgili Resmî Gazete maddeleri.",
                site + f"feeds/{VURGULU_KOD}.xml",
                adlar,
            ),
        )
    for k in etiketleyici.kategoriler:
        secili = [m for m in tumu if k.kod in m.get("kategoriler", [])]
        yaz(
            kok / "feeds" / f"{k.kod}.xml",
            rss_metni(
                secili[:KATEGORI_SINIR],
                f"Resmî Gazete — {k.ad}",
                k.aciklama or f"{k.ad} kategorisindeki Resmî Gazete maddeleri.",
                site + f"feeds/{k.kod}.xml",
                adlar,
            ),
        )
    return degisen
