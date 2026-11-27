"""Komut satırı: python -m rgtakip <komut>

  guncelle  Son N günü tarar, eksik günleri ve yeni mükerrerleri indirir, çıktıları üretir.
  turet     Ağa çıkmadan, kayıtlı gün dosyalarından türetilmiş dosyaları yeniden üretir.
  ozet      Son güncellemede gelen yeni maddelerin tek satırlık özetini yazar (commit mesajı).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import depo
from .etiket import VARSAYILAN_YOL, Etiketleyici
from .istemci import Istemci
from .toplayici import gun_topla, mukerrer_kontrol

# Türkiye 2016'dan beri sabit UTC+3 kullanıyor (yaz saati yok).
TR = timezone(timedelta(hours=3))
log = logging.getLogger("rgtakip")


def bugun_tr() -> date:
    return datetime.now(TR).date()


def turet_hepsi(etiketleyici: Etiketleyici) -> list[Path]:
    """Etiketleri güncel kurallarla yeniler ve bütün türetilmiş dosyaları üretir."""
    degisen: list[Path] = []
    gunler = depo.tum_gunler()
    for g in gunler:
        once = [m.get("kategoriler") for m in g["maddeler"]]
        for m in g["maddeler"]:
            m["kategoriler"] = etiketleyici.etiketle(m)
        if once != [m["kategoriler"] for m in g["maddeler"]] and depo.gun_yaz(g):
            degisen.append(depo.gun_yolu(date.fromisoformat(g["tarih"])))
    degisen += depo.turet(gunler, etiketleyici.ozet())
    return degisen


def komut_guncelle(args: argparse.Namespace) -> int:
    etiketleyici = Etiketleyici(args.kategoriler)
    istemci = Istemci(gecikme=args.gecikme)
    son = date.fromisoformat(args.tarih) if args.tarih else bugun_tr()
    yeni: list[dict] = []
    for geri in range(args.gun - 1, -1, -1):
        tarih = son - timedelta(days=geri)
        mevcut = depo.gun_oku(tarih)
        if mevcut is None:
            gun = gun_topla(istemci, tarih, etiketleyici, kurum=not args.kurumsuz)
            if gun is None:
                log.info("%s: gazete bulunamadı (henüz yayımlanmamış olabilir)", tarih)
                continue
            depo.gun_yaz(gun)
            yeni.extend(gun["maddeler"])
            log.info("%s: %d madde (%s)", tarih, gun["madde_sayisi"], ", ".join(str(s["sayi"]) for s in gun["sayilar"]))
        elif geri <= args.mukerrer_gun:
            ek = mukerrer_kontrol(istemci, mevcut, etiketleyici, kurum=not args.kurumsuz)
            if ek:
                depo.gun_yaz(mevcut)
                yeni.extend(ek)
                log.info("%s: %d yeni mükerrer madde", tarih, len(ek))
    turet_hepsi(etiketleyici)
    if args.yeni_dosya:
        Path(args.yeni_dosya).write_text(json.dumps({"maddeler": yeni}, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Bitti: %d yeni madde, %d istek", len(yeni), istemci.istek_sayisi)
    return 0


def komut_turet(args: argparse.Namespace) -> int:
    degisen = turet_hepsi(Etiketleyici(args.kategoriler))
    for y in degisen:
        print(y.relative_to(depo.KOK).as_posix())
    return 0


def ozet_metni(maddeler: list[dict], vurgulu: list[str]) -> str:
    if not maddeler:
        return "Resmî Gazete: yeni madde yok"
    tarihler = sorted({m["tarih"] for m in maddeler})
    sayilar = sorted({m["sayi"] for m in maddeler if m.get("sayi")})
    one_cikan = sum(1 for m in maddeler if set(m.get("kategoriler", [])) & set(vurgulu))
    if len(tarihler) == 1:
        t = date.fromisoformat(tarihler[0])
        bas = f"Resmî Gazete {t:%d.%m.%Y}"
    else:
        a, b = date.fromisoformat(tarihler[0]), date.fromisoformat(tarihler[-1])
        bas = f"Resmî Gazete {a:%d.%m.%Y}–{b:%d.%m.%Y}"
    sayi = f" (sayı {', '.join(map(str, sayilar[:3]))}{'…' if len(sayilar) > 3 else ''})" if sayilar else ""
    return f"{bas}{sayi}: {len(maddeler)} madde, {one_cikan} gümrük/dış ticaret"


def komut_ozet(args: argparse.Namespace) -> int:
    yol = Path(args.yeni_dosya)
    maddeler = json.loads(yol.read_text(encoding="utf-8"))["maddeler"] if yol.exists() else []
    print(ozet_metni(maddeler, Etiketleyici(args.kategoriler).vurgulu_kodlar()))
    return 0


def ana(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="rgtakip", description="Resmî Gazete takip aracı")
    p.add_argument("-v", "--ayrintili", action="store_true", help="hata ayıklama günlüğü")
    p.add_argument("--kategoriler", default=str(VARSAYILAN_YOL), help="kategori kuralları (YAML)")
    alt = p.add_subparsers(dest="komut", required=True)

    g = alt.add_parser("guncelle", help="yeni sayıları indir ve çıktıları üret")
    g.add_argument("--gun", type=int, default=30, help="geriye dönük kaç gün taransın (varsayılan 30)")
    g.add_argument("--mukerrer-gun", type=int, default=3, help="son kaç günde yeni mükerrer aransın")
    g.add_argument("--tarih", help="bitiş tarihi YYYY-AA-GG (varsayılan: bugün, TR saati)")
    g.add_argument("--gecikme", type=float, default=2.0, help="istekler arası bekleme (sn)")
    g.add_argument("--kurumsuz", action="store_true", help="kurum adı için belge metinlerini indirme")
    g.add_argument("--yeni-dosya", help="yeni maddeleri bu JSON dosyasına yaz")
    g.set_defaults(fn=komut_guncelle)

    t = alt.add_parser("turet", help="kayıtlı veriden türetilmiş dosyaları yeniden üret")
    t.set_defaults(fn=komut_turet)

    o = alt.add_parser("ozet", help="yeni maddelerin tek satırlık özeti")
    o.add_argument("yeni_dosya")
    o.set_defaults(fn=komut_ozet)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.ayrintili else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    return args.fn(args)
