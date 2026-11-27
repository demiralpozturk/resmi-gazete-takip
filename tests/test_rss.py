import xml.etree.ElementTree as ET
from datetime import date

from rgtakip import depo, rss
from rgtakip.etiket import Etiketleyici


def gunler():
    def m(id_, baslik, kat, sira):
        return {
            "id": id_, "tarih": "2026-11-27", "sayi": 33443, "mukerrer": 0, "sira": sira,
            "tur_kisa": "Tebliğ", "kurum": "Ticaret Bakanlığı", "baslik": baslik,
            "url": f"https://www.resmigazete.gov.tr/eskiler/2026/11/{id_}.htm", "kategoriler": kat,
        }
    return [depo.gun_olustur(date(2026, 11, 27), [{"sayi": 33443, "mukerrer": 0}], [
        m("20261127-1", "İthalatta Haksız Rekabet & Damping <Tebliğ>", ["dis-ticaret"], 1),
        m("20261127-2", "Tahsilat Genel Tebliği", ["vergi"], 2),
    ])]


def test_akislar(tmp_path):
    etk = Etiketleyici()
    degisen = rss.akislari_yaz(gunler(), etk, tmp_path)
    adlar = {p.relative_to(tmp_path).as_posix() for p in degisen}
    assert "feed.xml" in adlar and "feeds/dis-ticaret.xml" in adlar and "feeds/gumruk-dis-ticaret.xml" in adlar
    kok = ET.parse(tmp_path / "feed.xml").getroot()
    ogeler = kok.findall("./channel/item")
    assert [o.findtext("title") for o in ogeler] == ["İthalatta Haksız Rekabet & Damping <Tebliğ>", "Tahsilat Genel Tebliği"]
    assert ogeler[0].findtext("pubDate") == "Fri, 27 Nov 2026 00:00:00 +0300"
    assert "Ticaret Bakanlığı" in ogeler[0].findtext("description")
    vurgulu = ET.parse(tmp_path / "feeds" / "gumruk-dis-ticaret.xml").getroot().findall("./channel/item")
    assert len(vurgulu) == 1
    vergi = ET.parse(tmp_path / "feeds" / "vergi.xml").getroot().findall("./channel/item")
    assert [o.findtext("category") for o in vergi] == ["Vergi"]
    # Belirlenimci: ikinci çalıştırmada hiçbir dosya değişmemeli
    assert rss.akislari_yaz(gunler(), etk, tmp_path) == []


def test_site_adresi(monkeypatch):
    monkeypatch.delenv("RG_SITE_URL", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "Ornek/rg")
    assert rss.site_adresi() == "https://ornek.github.io/rg/"
    monkeypatch.setenv("RG_SITE_URL", "https://rg.example.com")
    assert rss.site_adresi() == "https://rg.example.com/"
