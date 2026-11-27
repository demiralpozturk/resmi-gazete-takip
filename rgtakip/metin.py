"""Türkçe metin yardımcıları: boşluk düzeltme, büyük/küçük harf ve aksan duyarsız karşılaştırma."""

from __future__ import annotations

import re

_BOSLUK = re.compile(r"\s+")
_SADE_TABLO = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)
_HARF_RAKAM_DISI = re.compile(r"[^a-z0-9]+")


def duzelt(metin: str | None) -> str:
    """Satır sonlarını, sert boşlukları ve fazla boşlukları tek boşluğa indirir."""
    if not metin:
        return ""
    return _BOSLUK.sub(" ", metin.replace("\xa0", " ")).strip()


def kucuk(metin: str) -> str:
    """Türkçe kurallarıyla küçük harf (I → ı, İ → i)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def buyuk(metin: str) -> str:
    """Türkçe kurallarıyla büyük harf (i → İ, ı → I)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def sade(metin: str | None) -> str:
    """Arama/eşleştirme için: küçük harf, Türkçe karakterler ASCII, noktalama boşluk."""
    if not metin:
        return ""
    s = kucuk(metin).translate(_SADE_TABLO)
    # Birleşik aksanları (ör. "i̇") at
    s = s.replace("̇", "")
    return _HARF_RAKAM_DISI.sub(" ", s).strip()


_KUCUK_KALSIN = {"ve", "ile", "ya", "da", "de", "veya", "ki"}


def baslik_harfi(metin: str) -> str:
    """'YÖNETMELİKLER' → 'Yönetmelikler' (Türkçe kurallarıyla, bağlaçlar küçük)."""
    kelimeler = []
    for i, k in enumerate(duzelt(metin).split(" ")):
        kk = kucuk(k)
        if i > 0 and kk in _KUCUK_KALSIN:
            kelimeler.append(kk)
        elif kk:
            kelimeler.append(buyuk(kk[0]) + kk[1:])
    return " ".join(kelimeler)
