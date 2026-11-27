import json
from datetime import date

import pytest

from rgtakip import depo
from rgtakip.cli import ozet_metni
from rgtakip.etiket import Etiketleyici
from rgtakip.metin import baslik_harfi, sade


@pytest.fixture(scope="module")
def etk():
    return Etiketleyici()


def madde(baslik, **ek):
    return {"baslik": baslik, "kurum": None, "tur": None, "bolum": "YÜRÜTME VE İDARE BÖLÜMÜ", **ek}


def test_sade():
    assert sade("İTHALATTA Haksız Rekabet") == "ithalatta haksiz rekabet"
    assert sade("Gümrük-İşbirliği") == "gumruk isbirligi"


def test_baslik_harfi():
    assert baslik_harfi("YÖNETMELİKLER") == "Yönetmelikler"
    assert baslik_harfi("YÜRÜTME VE İDARE BÖLÜMÜ") == "Yürütme ve İdare Bölümü"


@pytest.mark.parametrize(
    "baslik, olmali, olmamali",
    [
        ("İthalatta Haksız Rekabetin Önlenmesine İlişkin Tebliğ (No: 2026/33)", {"dis-ticaret"}, {"gumruk"}),
        (
            "AB-Türkiye Gümrük İşbirliği Komitesinin Yetkilendirilmiş Yükümlü Statüsü Programı ile … Kararının Onaylanması Hakkında Karar",
            {"gumruk"},
            set(),
        ),
        ("Kaynak Kullanımını Destekleme Fonu Kesintisi Hakkındaki Ekli Kararın Yürürlüğe Konulması", {"dis-ticaret", "finans"}, set()),
        ("Tahsilat Genel Tebliği (Seri:C Sıra No:10)", {"vergi"}, set()),
        ("Bina Yangın Yönetmeliği (Karar Sayısı: 12041)", {"imar"}, set()),
        ("Güvence Hesabı Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik", set(), {"imar"}),
        ("Borçlanma Araçlarının İhracına İlişkin Tebliğ", set(), {"dis-ticaret"}),
        ("Mustafa Kemal Üniversitesi Tekstil Sanatları Uygulama ve Araştırma Merkezi Yönetmeliği", {"egitim"}, set()),
        ("Bağlantı Anlaşması Uyarınca Tesis Edilecek 154 kV Diyarbakır GES TM Enerji İletim Hattı", {"enerji"}, set()),
        ("Harcama Belgeleri Yönetmeliği", set(), {"vergi"}),
    ],
)
def test_etiketler(etk, baslik, olmali, olmamali):
    k = set(etk.etiketle(madde(baslik)))
    assert olmali <= k, k
    assert not (olmamali & k), k


def test_yargi_bolumu(etk):
    assert "yargi" in etk.etiketle(madde("Anayasa Mahkemesinin Kararı", bolum="YARGI BÖLÜMÜ"))


def test_vurgulu(etk):
    assert set(etk.vurgulu_kodlar()) == {"gumruk", "dis-ticaret"}


def test_turet(tmp_path, etk):
    g1 = depo.gun_olustur(date(2026, 11, 26), [{"sayi": 1, "mukerrer": 0}], [madde("İthalat rejimi", id="a", tarih="2026-11-26", kategoriler=["dis-ticaret"], sira=1, mukerrer=0)])
    g2 = depo.gun_olustur(date(2026, 11, 27), [{"sayi": 2, "mukerrer": 0}], [madde("Vergi", id="b", tarih="2026-11-27", kategoriler=["vergi"], sira=1, mukerrer=0)])
    assert depo.gun_yaz(g1, tmp_path) and depo.gun_yaz(g2, tmp_path)
    assert not depo.gun_yaz(g2, tmp_path), "aynı içerik yeniden yazılmamalı"
    gunler = depo.tum_gunler(tmp_path)
    degisen = depo.turet(gunler, etk.ozet(), tmp_path)
    assert {p.name for p in degisen} == {"index.json", "latest.json", "son90.json", "kategoriler.json"}
    assert depo.turet(gunler, etk.ozet(), tmp_path) == [], "ikinci üretimde değişiklik olmamalı"
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["son_tarih"] == "2026-11-27" and index["gunler"][0]["tarih"] == "2026-11-27"
    son = json.loads((tmp_path / "son90.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in son["maddeler"]] == ["b", "a"]


def test_ozet_metni():
    m = [
        {"tarih": "2026-11-27", "sayi": 33443, "kategoriler": ["gumruk"]},
        {"tarih": "2026-11-27", "sayi": 33443, "kategoriler": ["vergi"]},
    ]
    assert ozet_metni(m, ["gumruk", "dis-ticaret"]) == "Resmî Gazete 27.11.2026 (sayı 33443): 2 madde, 1 gümrük/dış ticaret"
    assert ozet_metni([], []) == "Resmî Gazete: yeni madde yok"
