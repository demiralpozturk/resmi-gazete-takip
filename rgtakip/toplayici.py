"""Bir günün Resmî Gazete'sini (asıl + mükerrer sayılar) toplar."""

from __future__ import annotations

import logging
from datetime import date

from .ayristir import belge_kurumu, fihrist_ayristir
from .depo import gun_olustur
from .etiket import Etiketleyici
from .istemci import Istemci

log = logging.getLogger(__name__)

EN_FAZLA_MUKERRER = 10
GUNLUK_BELGE_SINIRI = 60


def _kurumlari_doldur(istemci: Istemci, maddeler: list[dict]) -> None:
    """HTM metinlerin başlığından kurum adını okur (gün başına sınırlı sayıda istek)."""
    sayac = 0
    for m in maddeler:
        if m.get("kurum") or m.get("bicim") != "htm" or m.get("tur_kisa") == "İlan":
            continue
        if sayac >= GUNLUK_BELGE_SINIRI:
            break
        sayac += 1
        try:
            html = istemci.belge(m["url"])
        except Exception as e:  # ağ hatası: kurum boş kalsın, toplama sürsün
            log.warning("Belge okunamadı (%s): %s", e, m["url"])
            continue
        if html:
            m["kurum"] = belge_kurumu(html)


def sayi_topla(istemci: Istemci, tarih: date, mukerrer: int, kurum: bool) -> dict | None:
    html = istemci.fihrist(tarih, mukerrer)
    if html is None:
        return None
    sonuc = fihrist_ayristir(html, tarih, mukerrer)
    if sonuc is None:
        return None
    if kurum:
        _kurumlari_doldur(istemci, sonuc["maddeler"])
    return sonuc


def gun_topla(istemci: Istemci, tarih: date, etiketleyici: Etiketleyici, kurum: bool = True) -> dict | None:
    """Günün asıl sayısını ve varsa mükerrerlerini toplar; gazete yoksa None."""
    asil = sayi_topla(istemci, tarih, 0, kurum)
    if asil is None:
        return None
    sayilar = [asil["sayi"]]
    maddeler = list(asil["maddeler"])
    for n in range(1, EN_FAZLA_MUKERRER + 1):
        ek = sayi_topla(istemci, tarih, n, kurum)
        if ek is None:
            break
        sayilar.append(ek["sayi"])
        maddeler.extend(ek["maddeler"])
    for m in maddeler:
        m["kategoriler"] = etiketleyici.etiketle(m)
    return gun_olustur(tarih, sayilar, maddeler)


def mukerrer_kontrol(istemci: Istemci, gun: dict, etiketleyici: Etiketleyici, kurum: bool = True) -> list[dict]:
    """Kayıtlı güne sonradan yayımlanan mükerrer sayıları ekler; yeni maddeleri döndürür."""
    tarih = date.fromisoformat(gun["tarih"])
    mevcut = max((s.get("mukerrer", 0) for s in gun["sayilar"]), default=0)
    yeni: list[dict] = []
    for n in range(mevcut + 1, EN_FAZLA_MUKERRER + 1):
        ek = sayi_topla(istemci, tarih, n, kurum)
        if ek is None:
            break
        for m in ek["maddeler"]:
            m["kategoriler"] = etiketleyici.etiketle(m)
        gun["sayilar"].append(ek["sayi"])
        gun["maddeler"].extend(ek["maddeler"])
        yeni.extend(ek["maddeler"])
    if yeni:
        gun.update(gun_olustur(tarih, gun["sayilar"], gun["maddeler"]))
    return yeni
