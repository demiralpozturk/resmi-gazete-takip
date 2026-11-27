import json

from rgtakip import telegram
from rgtakip.etiket import Etiketleyici


def madde(i, kat, tarih="2026-11-27"):
    return {
        "id": f"x{i}", "tarih": tarih, "sayi": 33443, "mukerrer": 0, "tur_kisa": "Tebliğ",
        "kurum": "Ticaret Bakanlığı", "baslik": f"Madde <{i}> & test",
        "url": f"https://www.resmigazete.gov.tr/eskiler/2026/11/20261127-{i}.htm", "kategoriler": kat,
    }


def test_secilenler_varsayilan_vurgulu():
    etk = Etiketleyici()
    m = [madde(1, ["gumruk"]), madde(2, ["vergi"]), madde(3, [])]
    assert [x["id"] for x in telegram.secilenler(m, etk, None)] == ["x1"]
    assert [x["id"] for x in telegram.secilenler(m, etk, "vergi")] == ["x2"]
    assert len(telegram.secilenler(m, etk, "hepsi")) == 3


def test_mesajlar_kacis_ve_bolme():
    m = [madde(i, ["gumruk"]) for i in range(200)]
    parcalar = telegram.mesajlar(m)
    assert len(parcalar) > 1
    assert all(len(p) <= 4096 for p in parcalar)
    assert "Madde &lt;1&gt; &amp; test" in parcalar[0]
    assert parcalar[0].startswith("<b>Resmî Gazete — 27.11.2026</b>")


def test_ayar_yoksa_atlar(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    yol = tmp_path / "yeni.json"
    yol.write_text(json.dumps({"maddeler": [madde(1, ["gumruk"])]}), encoding="utf-8")
    assert telegram.gonder(yol, Etiketleyici()) == 0
    assert "atlandı" in capsys.readouterr().out
