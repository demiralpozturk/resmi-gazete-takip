"""resmigazete.gov.tr için nazik HTTP istemcisi.

- İstekler sıralıdır, aralarında en az `gecikme` saniye beklenir.
- Geçici hatalarda (5xx, 429, bağlantı) artan beklemeyle yeniden dener.
- Kişisel bilgi içermeyen genel bir User-Agent kullanır.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date

import requests

KAYNAK = "https://www.resmigazete.gov.tr"
USER_AGENT = "Mozilla/5.0 (compatible; resmi-gazete-takip/1.0)"

log = logging.getLogger(__name__)


class Istemci:
    def __init__(self, gecikme: float = 2.0, zaman_asimi: float = 30.0, deneme: int = 3):
        self.gecikme = gecikme
        self.zaman_asimi = zaman_asimi
        self.deneme = deneme
        self.istek_sayisi = 0
        self._son = 0.0
        self.oturum = requests.Session()
        self.oturum.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9",
            }
        )

    def _bekle(self) -> None:
        fark = time.monotonic() - self._son
        if fark < self.gecikme:
            time.sleep(self.gecikme - fark)

    def getir(self, url: str, yonlendir: bool = True) -> requests.Response:
        hata: Exception | None = None
        for i in range(self.deneme):
            self._bekle()
            try:
                log.debug("GET %s", url)
                yanit = self.oturum.get(url, timeout=self.zaman_asimi, allow_redirects=yonlendir)
                self.istek_sayisi += 1
                self._son = time.monotonic()
                if yanit.status_code == 429 or yanit.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {yanit.status_code}: {url}", response=yanit)
                return yanit
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                self._son = time.monotonic()
                hata = e
                bekleme = self.gecikme * (3 ** (i + 1))
                log.warning("İstek başarısız (%s), %.0f sn sonra yeniden denenecek: %s", e, bekleme, url)
                if i < self.deneme - 1:
                    time.sleep(bekleme)
        assert hata is not None
        raise hata

    def fihrist(self, tarih: date, mukerrer: int = 0) -> str | None:
        """Günün fihrist sayfasını döndürür; o gün/mükerrer yoksa None.

        Site, olmayan bir sayı istendiğinde ana sayfaya yönlendirir (302).
        """
        url = f"{KAYNAK}/fihrist?tarih={tarih:%Y-%m-%d}"
        if mukerrer:
            url += f"&mukerrer={mukerrer}"
        yanit = self.getir(url, yonlendir=False)
        if 300 <= yanit.status_code < 400 or yanit.status_code == 404:
            return None
        yanit.raise_for_status()
        yanit.encoding = "utf-8"
        return yanit.text

    def belge(self, url: str) -> str | None:
        """Mevzuat metnini (HTM) indirip doğru kodlamayla çözer."""
        yanit = self.getir(url)
        if yanit.status_code != 200:
            return None
        return htm_coz(yanit.content)


def htm_coz(icerik: bytes) -> str:
    """Eski HTM belgeleri çoğunlukla windows-1254; meta etiketine bakarak çözer."""
    m = re.search(rb"charset\s*=\s*[\"']?([\w-]+)", icerik[:4000], re.I)
    kodlama = m.group(1).decode("ascii", "ignore") if m else "windows-1254"
    try:
        return icerik.decode(kodlama, errors="replace")
    except LookupError:
        return icerik.decode("windows-1254", errors="replace")
