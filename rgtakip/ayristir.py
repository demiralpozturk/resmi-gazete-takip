"""Resmî Gazete fihrist sayfasını ve mevzuat metinlerini ayrıştırır."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .istemci import KAYNAK
from .metin import baslik_harfi, buyuk, duzelt

_SAYI = re.compile(r"Tarihli\s+ve\s+(\d+)\s+Say[ıi]l[ıi]", re.I)
_MUKERRER = re.compile(r"(\d+)\s*\.\s*M[üu]kerrer", re.I)
_BAS_TIRE = re.compile(r"^[\s\-–—−•·]+")
_ILAN_HARF = re.compile(r"^[a-zçğıöşü]\s*[-–]\s+", re.I)


def fihrist_ayristir(html: str, tarih: date, mukerrer: int = 0) -> dict | None:
    """Fihrist sayfasından sayı bilgisini ve maddeleri çıkarır.

    Dönüş: {"sayi": {...}, "maddeler": [...]}; madde yoksa None.
    """
    corba = BeautifulSoup(html, "lxml")
    icerik = corba.find(id="html-content")
    if icerik is None:
        return None

    ust = corba.select_one(".preview-title") or corba.find(id="spanGazeteTarih")
    ust_metin = duzelt(ust.get_text(" ")) if ust else ""
    ust_metin = re.sub(r"\s*PDF\s+G[öo]r[üu]nt[üu]le.*$", "", ust_metin, flags=re.I)
    m = _SAYI.search(ust_metin)
    sayi_no = int(m.group(1)) if m else None
    m = _MUKERRER.search(ust_metin)
    if m:
        mukerrer = int(m.group(1))
    pdf = None
    if ust:
        for a in ust.find_all("a", href=True):
            if a["href"].lower().endswith(".pdf"):
                pdf = urljoin(KAYNAK, a["href"])
                break

    maddeler: list[dict] = []
    bolum: str | None = None
    tur: str | None = None
    grup: str | None = None
    for el in icerik.select(".html-title, .html-subtitle, .fihrist-item"):
        siniflar = el.get("class", [])
        metin = duzelt(el.get_text(" "))
        if not metin:
            continue
        if "html-title" in siniflar:
            bolum, tur, grup = metin, None, None
            continue
        if "html-subtitle" in siniflar:
            tur, grup = metin, None
            continue
        a = el.find("a", href=True)
        if a is None:
            # Bağlantısız satır: alt grup başlığı (ör. "Ticaret Bakanlığına Ait Tebliğler")
            grup = _BAS_TIRE.sub("", metin)
            continue
        url = _gercek_url(a["href"])
        baslik = _BAS_TIRE.sub("", metin)
        if bolum and "İLÂN" in buyuk(bolum).replace("İLAN", "İLÂN"):
            baslik = _ILAN_HARF.sub("", baslik)
        madde = {
            "id": _madde_id(url, tarih, mukerrer, len(maddeler) + 1),
            "tarih": tarih.isoformat(),
            "sayi": sayi_no,
            "mukerrer": mukerrer,
            "bolum": bolum,
            "tur": tur,
            "tur_kisa": tur_kisa(tur, bolum),
            "baslik": baslik,
            "kurum": kurum_tahmin(tur, bolum, baslik),
            "url": url,
            "bicim": _bicim(url),
            "sira": len(maddeler) + 1,
        }
        if grup:
            madde["grup"] = grup
        maddeler.append(madde)

    if not maddeler:
        return None
    sayi = {
        "sayi": sayi_no,
        "mukerrer": mukerrer,
        "baslik": ust_metin or None,
        "pdf": pdf,
        "fihrist": f"{KAYNAK}/fihrist?tarih={tarih:%Y-%m-%d}" + (f"&mukerrer={mukerrer}" if mukerrer else ""),
        "madde_sayisi": len(maddeler),
    }
    return {"sayi": sayi, "maddeler": maddeler}


def _gercek_url(href: str) -> str:
    url = urljoin(KAYNAK + "/", href.strip())
    # Eski ilan bağlantıları: main.aspx?home=...&main=<asıl adres>
    if "main.aspx" in url.lower():
        q = parse_qs(urlparse(url).query)
        if q.get("main"):
            url = q["main"][0]
    return url.replace("http://", "https://", 1)


def _bicim(url: str) -> str:
    yol = urlparse(url).path.lower()
    if yol.endswith(".pdf"):
        return "pdf"
    if yol.endswith((".htm", ".html")):
        return "htm"
    return "diger"


def _madde_id(url: str, tarih: date, mukerrer: int, sira: int) -> str:
    yol = urlparse(url).path
    ad = yol.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if re.fullmatch(r"\d{8}(M\d+)?(-\d+)?", ad or ""):
        return ("ilan-" if "/ilanlar/" in yol else "") + ad
    ek = f"M{mukerrer}" if mukerrer else ""
    return f"{tarih:%Y%m%d}{ek}-x{sira}"


def tur_kisa(tur: str | None, bolum: str | None) -> str:
    """Fihristteki tür başlığını sade bir türe indirger (filtre için)."""
    t = buyuk(tur or "")
    b = buyuk(bolum or "")
    if "İLÂN" in b or "İLAN" in b:
        return "İlan"
    kurallar = [
        ("HÜKMÜNDE", "Kanun Hükmünde Kararname"),
        ("KARARNAME", "Cumhurbaşkanlığı Kararnamesi"),
        ("ANDLAŞMA", "Milletlerarası Andlaşma"),
        ("ANTLAŞMA", "Milletlerarası Andlaşma"),
        ("YÖNETMELİK", "Yönetmelik"),
        ("TEBLİĞ", "Tebliğ"),
        ("GENELGE", "Genelge"),
        ("ATAMA", "Atama Kararı"),
    ]
    for anahtar, deger in kurallar:
        if anahtar in t:
            return deger
    if "YARGI" in b:
        return "Yargı Kararı"
    if "KANUN" in t:
        return "Kanun"
    if "KARAR" in t:
        return "Karar"
    return baslik_harfi(tur) if tur else "Diğer"


def kurum_tahmin(tur: str | None, bolum: str | None, baslik: str) -> str | None:
    """Belgeyi açmadan, tür ve başlıktan çıkarılabilen kurum."""
    t = buyuk(tur or "")
    b = buyuk(bolum or "")
    bs = buyuk(baslik)
    if "HÂKİMLER VE SAVCILAR KURULU" in bs or "HAKİMLER VE SAVCILAR KURULU" in bs:
        return "Hâkimler ve Savcılar Kurulu"
    if "MERKEZ BANKASI" in bs and ("DÖVİZ" in bs or "KUR" in bs):
        return "Türkiye Cumhuriyet Merkez Bankası"
    yargi = "YARGI" in b
    if bs.startswith("ANAYASA MAHKEMESİ") or (yargi and "ANAYASA MAHKEMESİ" in t):
        return "Anayasa Mahkemesi"
    if bs.startswith("YARGITAY") or (yargi and "YARGITAY" in t):
        return "Yargıtay"
    if bs.startswith("DANIŞTAY") or (yargi and "DANIŞTAY" in t):
        return "Danıştay"
    if yargi and "UYUŞMAZLIK" in t:
        return "Uyuşmazlık Mahkemesi"
    if any(k in t for k in ("CUMHURBAŞKANI", "CUMHURBAŞKANLIĞI", "ANDLAŞMA", "ATAMA", "GENELGE")):
        return "Cumhurbaşkanlığı"
    if "KARAR SAYISI" in bs:
        # Cumhurbaşkanı kararıyla yürürlüğe konulan yönetmelik vb.
        return "Cumhurbaşkanlığı"
    if t.startswith("KANUN") and "HÜKMÜNDE" not in t:
        return "Türkiye Büyük Millet Meclisi"
    return None


_ABLATIF = re.compile(r"^(?P<ad>.+?)(?P<ek>[’']\s*n?[dt][ae]n|n[dt][ae]n|[dt][ae]n)$")
_BUYUK_KELIME = re.compile(r"^[A-ZÇĞİÖŞÜÂÎÛ0-9.,()/\-]+$")


def belge_kurumu(html: str) -> str | None:
    """Mevzuat metninin başındaki "… Bakanlığından:" satırından kurumu bulur."""
    corba = BeautifulSoup(html, "lxml")
    metin = duzelt(corba.get_text(" "))
    # "Başkanlığı)’ ndan :" gibi bölünmüş ekleri birleştir
    metin = re.sub(r"\s*([’'])\s*(n?[dt][ae]n)\s*:", r"\1\2:", metin)
    metin = re.sub(r"\s+:", ":", metin)
    m = re.search(r"Say[ıi]\s*:\s*\d+(?:\s*\(\s*\d+\s*\.\s*M[üu]kerrer\s*\))?", metin)
    if not m:
        return None
    sonrasi = metin[m.end() : m.end() + 400]
    iki_nokta = sonrasi.find(":")
    if iki_nokta < 0:
        return None
    aday = sonrasi[:iki_nokta].strip()
    # Baştaki tamamı büyük harfli tür başlığını (TEBLİĞ, YÖNETMELİK, KURUL KARARI …) at
    kelimeler = aday.split(" ")
    while kelimeler and _BUYUK_KELIME.match(kelimeler[0]) and len(kelimeler) > 1:
        kelimeler.pop(0)
    aday = " ".join(kelimeler).strip()
    return yalin_hal(aday)


def yalin_hal(ad: str) -> str | None:
    """'Ticaret Bakanlığından' → 'Ticaret Bakanlığı'; ek yoksa None."""
    ad = duzelt(ad)
    if not ad or len(ad) > 160:
        return None
    m = _ABLATIF.match(ad)
    if not m:
        return None
    govde, ek = m.group("ad"), m.group("ek")
    if ek[0] in "’'":
        return govde.strip()
    if ek.startswith("n"):
        # Bakanlığı+ndan, Üniversitesi+nden: n kaynaştırma harfi
        if govde and govde[-1] in "aeıioöuüâîû":
            return govde
        return govde + "n"
    return govde
