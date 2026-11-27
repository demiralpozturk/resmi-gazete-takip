"""Gün dosyalarını yazar/okur ve türetilmiş dosyaları (index, latest, son90) üretir.

Dosyalar yalnızca içerik gerçekten değiştiğinde yazılır; böylece Actions'ta
boş/sahte commit oluşmaz.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
VERI = KOK / "data"
SON_GUN_SAYISI = 90


def gun_yolu(tarih: date, kok: Path = VERI) -> Path:
    return kok / f"{tarih:%Y}" / f"{tarih:%m}" / f"{tarih:%d}.json"


def json_metni(veri) -> str:
    return json.dumps(veri, ensure_ascii=False, indent=1) + "\n"


def yaz_degistiyse(yol: Path, metin: str) -> bool:
    """Dosya içeriği farklıysa yazar; yazdıysa True."""
    if yol.exists() and yol.read_text(encoding="utf-8") == metin:
        return False
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8", newline="\n")
    return True


def gun_oku(tarih: date, kok: Path = VERI) -> dict | None:
    yol = gun_yolu(tarih, kok)
    if not yol.exists():
        return None
    return json.loads(yol.read_text(encoding="utf-8"))


def gun_yaz(gun: dict, kok: Path = VERI) -> bool:
    tarih = date.fromisoformat(gun["tarih"])
    return yaz_degistiyse(gun_yolu(tarih, kok), json_metni(gun))


def tum_gunler(kok: Path = VERI) -> list[dict]:
    """Bütün gün dosyaları, eskiden yeniye."""
    gunler = []
    for yol in sorted(kok.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9].json")):
        gunler.append(json.loads(yol.read_text(encoding="utf-8")))
    gunler.sort(key=lambda g: g["tarih"])
    return gunler


def gun_olustur(tarih: date, sayilar: list[dict], maddeler: list[dict]) -> dict:
    sayilar = sorted(sayilar, key=lambda s: s.get("mukerrer", 0))
    return {
        "tarih": tarih.isoformat(),
        "sayilar": sayilar,
        "madde_sayisi": len(maddeler),
        "maddeler": maddeler,
    }


def turet(gunler: list[dict], kategori_ozet: list[dict], kok: Path = VERI) -> list[Path]:
    """index.json, latest.json, son90.json ve kategoriler.json üretir. Değişen yolları döndürür."""
    degisen: list[Path] = []
    if not gunler:
        return degisen

    sayac_toplam: dict[str, int] = {}
    index = []
    for g in gunler:
        sayac: dict[str, int] = {}
        for m in g["maddeler"]:
            for k in m.get("kategoriler", []):
                sayac[k] = sayac.get(k, 0) + 1
                sayac_toplam[k] = sayac_toplam.get(k, 0) + 1
        index.append(
            {
                "tarih": g["tarih"],
                "sayilar": [
                    {"sayi": s.get("sayi"), "mukerrer": s.get("mukerrer", 0), "pdf": s.get("pdf")} for s in g["sayilar"]
                ],
                "madde_sayisi": g["madde_sayisi"],
                "kategoriler": dict(sorted(sayac.items())),
                "dosya": f"data/{g['tarih'][:4]}/{g['tarih'][5:7]}/{g['tarih'][8:10]}.json",
            }
        )
    index.reverse()  # yeniden eskiye

    son_tarih = date.fromisoformat(gunler[-1]["tarih"])
    sinir = son_tarih - timedelta(days=SON_GUN_SAYISI - 1)
    son_maddeler = []
    for g in reversed(gunler):
        if date.fromisoformat(g["tarih"]) < sinir:
            break
        son_maddeler.extend(sorted(g["maddeler"], key=lambda m: (-m.get("mukerrer", 0), m.get("sira", 0))))

    dosyalar = {
        kok / "index.json": {
            "son_tarih": gunler[-1]["tarih"],
            "ilk_tarih": gunler[0]["tarih"],
            "gun_sayisi": len(gunler),
            "gunler": index,
        },
        kok / "latest.json": gunler[-1],
        kok / f"son{SON_GUN_SAYISI}.json": {
            "baslangic": sinir.isoformat(),
            "bitis": son_tarih.isoformat(),
            "madde_sayisi": len(son_maddeler),
            "maddeler": son_maddeler,
        },
        kok / "kategoriler.json": [
            {**k, "toplam": sayac_toplam.get(k["kod"], 0)} for k in kategori_ozet
        ],
    }
    for yol, veri in dosyalar.items():
        if yaz_degistiyse(yol, json_metni(veri)):
            degisen.append(yol)
    return degisen
