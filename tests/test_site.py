import pytest

from rgtakip import depo, site


def test_site_kur(tmp_path):
    cikti = site.site_kur(tmp_path / "s")
    for ad in ("index.html", "app.js", "style.css", ".nojekyll"):
        assert (cikti / ad).exists(), ad
    html = (cikti / "index.html").read_text(encoding="utf-8")
    assert "Demiralp Öztürk" in html and "resmî olmayan" in html.lower()
    assert 'src="app.js?v=' in html and 'href="style.css?v=' in html


@pytest.mark.parametrize("ad", ["docs", "data", "rgtakip"])
def test_kaynak_klasore_yazmaz(ad):
    with pytest.raises(ValueError):
        site.site_kur(depo.KOK / ad)


def test_koke_yazmaz():
    with pytest.raises(ValueError):
        site.site_kur(depo.KOK)
