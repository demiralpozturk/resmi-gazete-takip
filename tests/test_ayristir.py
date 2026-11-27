from datetime import date
from pathlib import Path

import pytest

from rgtakip.ayristir import belge_kurumu, fihrist_ayristir, tur_kisa, yalin_hal
from rgtakip.istemci import htm_coz

ORNEK = Path(__file__).parent / "ornekler"


def oku(ad: str) -> str:
    return (ORNEK / ad).read_text(encoding="utf-8")


def belge(ad: str) -> str:
    return htm_coz((ORNEK / ad).read_bytes())


@pytest.fixture(scope="module")
def gun_26():
    return fihrist_ayristir(oku("fihrist-2026-11-26.html"), date(2026, 11, 26))


def test_sayi_bilgisi(gun_26):
    s = gun_26["sayi"]
    assert s["sayi"] == 33442
    assert s["mukerrer"] == 0
    assert s["madde_sayisi"] == 16
    assert s["fihrist"].endswith("fihrist?tarih=2026-11-26")
    assert s["baslik"] == "26 Kasım 2026 Tarihli ve 33442 Sayılı Resmî Gazete"


def test_yonetmelik_ve_teblig(gun_26):
    m = gun_26["maddeler"]
    assert m[0]["bolum"] == "YÜRÜTME VE İDARE BÖLÜMÜ"
    assert m[0]["tur_kisa"] == "Yönetmelik"
    assert m[0]["baslik"].startswith("Hatay Mustafa Kemal Üniversitesi")
    teblig = m[3]
    assert teblig["baslik"] == "İthalatta Haksız Rekabetin Önlenmesine İlişkin Tebliğ (No: 2026/33)"
    assert teblig["tur_kisa"] == "Tebliğ"
    assert teblig["id"] == "20261126-4"
    assert teblig["url"] == "https://www.resmigazete.gov.tr/eskiler/2026/11/20261126-4.htm"
    assert teblig["bicim"] == "htm"


def test_yargi_kararlari(gun_26):
    aym = [m for m in gun_26["maddeler"] if m["kurum"] == "Anayasa Mahkemesi"]
    assert len(aym) == 7
    assert all(m["bicim"] == "pdf" and m["tur_kisa"] == "Yargı Kararı" for m in aym)
    assert any(m["kurum"] == "Yargıtay" for m in gun_26["maddeler"])


def test_ilan_bolumu(gun_26):
    ilanlar = [m for m in gun_26["maddeler"] if m["tur_kisa"] == "İlan"]
    assert [m["baslik"] for m in ilanlar[:3]] == [
        "Yargı İlânları",
        "Artırma, Eksiltme ve İhale İlânları",
        "Çeşitli İlânlar",
    ]
    assert ilanlar[0]["id"] == "ilan-20261126-2"
    kur = ilanlar[-1]
    assert kur["baslik"].startswith("T.C. Merkez Bankasınca Belirlenen Döviz Kurları")
    assert kur["kurum"] == "Türkiye Cumhuriyet Merkez Bankası"


def test_mukerrer_sayi():
    g = fihrist_ayristir(oku("fihrist-2026-10-27-m1.html"), date(2026, 10, 27), mukerrer=1)
    assert g["sayi"]["sayi"] == 33413
    assert g["sayi"]["mukerrer"] == 1
    (m,) = g["maddeler"]
    assert m["id"] == "20261027M1-1"
    assert m["mukerrer"] == 1
    assert m["tur_kisa"] == "Karar"
    assert m["kurum"] == "Cumhurbaşkanlığı"
    assert "Yıllık Programının Onaylanması" in m["baslik"]


def test_ana_sayfa_ayni_bicim():
    g = fihrist_ayristir(oku("fihrist-2026-11-27-anasayfa.html"), date(2026, 11, 27))
    assert g["sayi"]["sayi"] == 33443
    turler = {m["tur_kisa"] for m in g["maddeler"]}
    assert {"Milletlerarası Andlaşma", "Karar", "Yönetmelik", "Tebliğ", "Atama Kararı", "Yargı Kararı", "İlan"} <= turler
    assert any("Gümrük İşbirliği Komitesinin" in m["baslik"] for m in g["maddeler"])
    hsk = next(m for m in g["maddeler"] if "Yargıtay Üyeliklerine" in m["baslik"])
    assert hsk["kurum"] == "Hâkimler ve Savcılar Kurulu"
    assert hsk["tur_kisa"] == "Karar"


def test_bos_sayfa():
    assert fihrist_ayristir("<html><body>yok</body></html>", date(2026, 1, 1)) is None


@pytest.mark.parametrize(
    "dosya, kurum",
    [
        ("belge-20261126-4.htm", "Ticaret Bakanlığı"),
        ("belge-20261127-22.htm", "Hazine ve Maliye Bakanlığı (Gelir İdaresi Başkanlığı)"),
        ("belge-20261126-2.htm", "Hatay Mustafa Kemal Üniversitesi"),
    ],
)
def test_belge_kurumu(dosya, kurum):
    assert belge_kurumu(belge(dosya)) == kurum


@pytest.mark.parametrize(
    "girdi, beklenen",
    [
        ("Ticaret Bakanlığından", "Ticaret Bakanlığı"),
        ("Rekabet Kurumundan", "Rekabet Kurumu"),
        ("Enerji Piyasası Düzenleme Kurulundan", "Enerji Piyasası Düzenleme Kurulu"),
        ("Sayıştaydan", "Sayıştay"),
        ("Türkiye Cumhuriyet Merkez Bankasından", "Türkiye Cumhuriyet Merkez Bankası"),
        ("Hazine ve Maliye Bakanlığı (Gelir İdaresi Başkanlığı)’ndan", "Hazine ve Maliye Bakanlığı (Gelir İdaresi Başkanlığı)"),
        ("Karar Sayısı", None),
    ],
)
def test_yalin_hal(girdi, beklenen):
    assert yalin_hal(girdi) == beklenen


def test_tur_kisa():
    assert tur_kisa("KANUN HÜKMÜNDE KARARNAME", None) == "Kanun Hükmünde Kararname"
    assert tur_kisa("CUMHURBAŞKANLIĞI KARARNAMESİ", None) == "Cumhurbaşkanlığı Kararnamesi"
    assert tur_kisa("KANUNLAR", None) == "Kanun"
    assert tur_kisa("GENELGE", None) == "Genelge"
    assert tur_kisa(None, "İLÂN BÖLÜMÜ") == "İlan"
    assert tur_kisa("KURUL KARARLARI", None) == "Karar"


@pytest.mark.parametrize(
    "baslik, kurum",
    [
        ("Enerji Piyasası Düzenleme Kurulunun 19/11/2026 Tarihli ve 15055 Sayılı Kararı", "Enerji Piyasası Düzenleme Kurulu"),
        ("Bankacılık Düzenleme ve Denetleme Kurulunun 17/11/2026 Tarihli ve 11601 Sayılı Kararı", "Bankacılık Düzenleme ve Denetleme Kurulu"),
        ("Özelleştirme İdaresi Başkanlığının 30/10/2026 Tarihli ve 2026/ÖİB-K-46 Sayılı Kararı", "Özelleştirme İdaresi Başkanlığı"),
        (
            "Kamu Gözetimi, Muhasebe ve Denetim Standartları Kurulunun 30/10/2026 Tarihli ve 75935942-050.01.04-[01/47239] Sayılı Kararı",
            "Kamu Gözetimi, Muhasebe ve Denetim Standartları Kurulu",
        ),
        ("Sayıştay’ın 1/2/2026 Tarihli Kararı", "Sayıştay"),
        ("Ozan Elektronik Para A.Ş.’nin Faaliyet İzninin İptal Edilmesine İlişkin Karar", None),
    ],
)
def test_baslikta_kurum(baslik, kurum):
    from rgtakip.ayristir import kurum_tahmin

    assert kurum_tahmin("KURUL KARARLARI", "YÜRÜTME VE İDARE BÖLÜMÜ", baslik) == kurum
