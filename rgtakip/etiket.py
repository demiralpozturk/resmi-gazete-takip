"""config/kategoriler.yml'deki kurallarla maddeleri konu kategorilerine etiketler.

Eşleştirme büyük/küçük harf ve Türkçe karakter duyarsızdır ("GÜMRÜK" = "gumruk").
- anahtar_kelimeler: kelime başında eşleşir, ek alabilir ("ithalat" → "ithalatta").
- tam_kelimeler: yalnız kelimenin tamamı (kısaltmalar için: KDV, GES, SPK …).
- haric: bunlardan biri geçerse o kategori verilmez.
- turler / bolumler / kurumlar: fihristteki tür, bölüm veya kurum adında geçerse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .metin import sade

VARSAYILAN_YOL = Path(__file__).resolve().parent.parent / "config" / "kategoriler.yml"


def _bas(kelime) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(sade(str(kelime))))


def _tam(kelime) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(sade(str(kelime))) + r"(?![a-z0-9])")


@dataclass
class Kategori:
    kod: str
    ad: str
    aciklama: str = ""
    renk: str = "#64748b"
    vurgulu: bool = False
    desenler: list[re.Pattern] = field(default_factory=list)
    haric: list[re.Pattern] = field(default_factory=list)
    turler: list[str] = field(default_factory=list)
    bolumler: list[str] = field(default_factory=list)
    kurumlar: list[str] = field(default_factory=list)

    def eslesir(self, madde: dict) -> bool:
        metin = sade(" ".join(filter(None, [madde.get("baslik"), madde.get("kurum"), madde.get("grup")])))
        if any(d.search(metin) for d in self.haric):
            return False
        if any(d.search(metin) for d in self.desenler):
            return True
        tur = sade(madde.get("tur"))
        if tur and any(t in tur for t in self.turler):
            return True
        bolum = sade(madde.get("bolum"))
        if bolum and any(b in bolum for b in self.bolumler):
            return True
        kurum = sade(madde.get("kurum"))
        if kurum and any(k in kurum for k in self.kurumlar):
            return True
        return False

    def ozet(self) -> dict:
        return {"kod": self.kod, "ad": self.ad, "aciklama": self.aciklama, "renk": self.renk, "vurgulu": self.vurgulu}


class Etiketleyici:
    def __init__(self, yol: Path | str = VARSAYILAN_YOL):
        veri = yaml.safe_load(Path(yol).read_text(encoding="utf-8")) or {}
        self.kategoriler: list[Kategori] = []
        for kod, k in (veri.get("kategoriler") or {}).items():
            if not re.fullmatch(r"[a-z0-9-]+", kod):
                raise ValueError(f"Kategori kodu yalnız küçük harf, rakam ve tire içermeli: {kod!r}")
            k = k or {}
            self.kategoriler.append(
                Kategori(
                    kod=kod,
                    ad=k.get("ad", kod),
                    aciklama=k.get("aciklama", ""),
                    renk=k.get("renk", "#64748b"),
                    vurgulu=bool(k.get("vurgulu", False)),
                    desenler=[_bas(x) for x in k.get("anahtar_kelimeler", []) or []]
                    + [_tam(x) for x in k.get("tam_kelimeler", []) or []],
                    haric=[_bas(x) for x in k.get("haric", []) or []],
                    turler=[sade(str(x)) for x in k.get("turler", []) or []],
                    bolumler=[sade(str(x)) for x in k.get("bolumler", []) or []],
                    kurumlar=[sade(str(x)) for x in k.get("kurumlar", []) or []],
                )
            )

    def etiketle(self, madde: dict) -> list[str]:
        return [k.kod for k in self.kategoriler if k.eslesir(madde)]

    def vurgulu_kodlar(self) -> list[str]:
        return [k.kod for k in self.kategoriler if k.vurgulu]

    def ozet(self) -> list[dict]:
        return [k.ozet() for k in self.kategoriler]
