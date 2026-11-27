/* Resmî Gazete Takip — istemci tarafı arama ve filtre (bağımlılıksız). */
(() => {
  "use strict";

  const SAYFA = 60;
  const EN_FAZLA_GUN_INDIR = 62;
  const VURGULU_AKIS = "feeds/gumruk-dis-ticaret.xml";

  const $ = (s) => document.querySelector(s);
  const durum = {
    index: null,
    kategoriler: [],
    katHarita: new Map(),
    vurgulu: new Set(),
    maddeler: [],
    yuklenenGunler: new Set(),
    sayiBilgisi: new Map(), // tarih -> sayilar[]
    limit: SAYFA,
    suzgec: { q: "", t1: "", t2: "", tur: "", bolum: "", kat: new Set(), yalnizVurgulu: false },
  };

  // ---------- yardımcılar ----------
  const SADE = { "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u" };
  function sade(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/I/g, "ı").replace(/İ/g, "i").toLowerCase()
      .replace(/[çğıöşüâîû]/g, (c) => SADE[c]).replace(/̇/g, "")
      .replace(/[^a-z0-9]+/g, " ").trim();
  }

  function h(etiket, ozellik, ...cocuklar) {
    const el = document.createElement(etiket);
    for (const [k, v] of Object.entries(ozellik || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of cocuklar.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  const tarihBicim = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "long", year: "numeric", weekday: "long", timeZone: "UTC" });
  const kisaTarih = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const sayiBicim = new Intl.NumberFormat("tr-TR");
  const tarihYaz = (iso, bicim = tarihBicim) => bicim.format(new Date(iso + "T00:00:00Z"));
  const gunEkle = (iso, n) => { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
  const gunYolu = (iso) => `data/${iso.slice(0, 4)}/${iso.slice(5, 7)}/${iso.slice(8, 10)}.json`;

  async function jsonAl(yol) {
    const y = await fetch(yol, { cache: "no-cache" });
    if (!y.ok) throw new Error(`${yol}: HTTP ${y.status}`);
    return y.json();
  }

  function hazirla(m) {
    m._ara = sade([m.baslik, m.kurum, m.tur_kisa, m.tur, m.grup, m.id, m.sayi ? `sayi ${m.sayi}` : ""].join(" "));
    return m;
  }

  function sirala() {
    durum.maddeler.sort((a, b) =>
      a.tarih < b.tarih ? 1 : a.tarih > b.tarih ? -1 : (b.mukerrer || 0) - (a.mukerrer || 0) || (a.sira || 0) - (b.sira || 0));
  }

  // ---------- tema ----------
  function temaKur() {
    const kayitli = localStorage.getItem("rg-tema");
    if (kayitli) document.documentElement.dataset.tema = kayitli;
    $("#tema").addEventListener("click", () => {
      const koyuMu = document.documentElement.dataset.tema
        ? document.documentElement.dataset.tema === "koyu"
        : matchMedia("(prefers-color-scheme: dark)").matches;
      const yeni = koyuMu ? "acik" : "koyu";
      document.documentElement.dataset.tema = yeni;
      localStorage.setItem("rg-tema", yeni);
    });
  }

  // ---------- URL durumu ----------
  function hashOku() {
    const p = new URLSearchParams(location.hash.slice(1));
    const s = durum.suzgec;
    s.q = p.get("q") || "";
    s.t1 = p.get("t1") || "";
    s.t2 = p.get("t2") || "";
    s.tur = p.get("tur") || "";
    s.bolum = p.get("bolum") || "";
    s.kat = new Set((p.get("k") || "").split(",").filter(Boolean));
    s.yalnizVurgulu = p.get("v") === "1";
  }

  function hashYaz() {
    const s = durum.suzgec;
    const p = new URLSearchParams();
    if (s.q) p.set("q", s.q);
    if (s.t1) p.set("t1", s.t1);
    if (s.t2) p.set("t2", s.t2);
    if (s.tur) p.set("tur", s.tur);
    if (s.bolum) p.set("bolum", s.bolum);
    if (s.kat.size) p.set("k", [...s.kat].join(","));
    if (s.yalnizVurgulu) p.set("v", "1");
    const yeni = p.toString();
    history.replaceState(null, "", yeni ? "#" + yeni : location.pathname + location.search);
  }

  function formuDoldur() {
    const s = durum.suzgec;
    $("#q").value = s.q;
    $("#t1").value = s.t1;
    $("#t2").value = s.t2;
    $("#tur").value = s.tur;
    $("#bolum").value = s.bolum;
    $("#yalniz-vurgulu").checked = s.yalnizVurgulu;
  }

  // ---------- veri ----------
  async function eksikGunleriYukle() {
    const s = durum.suzgec;
    if (!s.t1 || !durum.index) return;
    const bitis = s.t2 || durum.index.son_tarih;
    const gerekli = durum.index.gunler
      .map((g) => g.tarih)
      .filter((t) => t >= s.t1 && t <= bitis && !durum.yuklenenGunler.has(t))
      .slice(0, EN_FAZLA_GUN_INDIR);
    if (!gerekli.length) return;
    $("#sonuc-ozet").textContent = `${gerekli.length} gün yükleniyor…`;
    const sonuclar = await Promise.allSettled(gerekli.map((t) => jsonAl(gunYolu(t))));
    for (const r of sonuclar) {
      if (r.status !== "fulfilled") continue;
      const gun = r.value;
      durum.yuklenenGunler.add(gun.tarih);
      durum.sayiBilgisi.set(gun.tarih, gun.sayilar);
      for (const m of gun.maddeler) durum.maddeler.push(hazirla(m));
    }
    sirala();
    secenekleriDoldur();
  }

  // ---------- filtre ----------
  function suz() {
    const s = durum.suzgec;
    const kelimeler = sade(s.q).split(" ").filter(Boolean);
    return durum.maddeler.filter((m) => {
      if (s.t1 && m.tarih < s.t1) return false;
      if (s.t2 && m.tarih > s.t2) return false;
      if (s.tur && m.tur_kisa !== s.tur) return false;
      if (s.bolum && m.bolum !== s.bolum) return false;
      const kat = m.kategoriler || [];
      if (s.yalnizVurgulu && !kat.some((k) => durum.vurgulu.has(k))) return false;
      if (s.kat.size && !kat.some((k) => s.kat.has(k))) return false;
      for (const k of kelimeler) if (!m._ara.includes(k)) return false;
      return true;
    });
  }

  // ---------- çizim ----------
  function katCip(kod, tiklanabilir = true) {
    const k = durum.katHarita.get(kod);
    if (!k) return null;
    return h("button", {
      class: "cip", type: "button", style: `--renk:${k.renk}`,
      "aria-pressed": durum.suzgec.kat.has(kod) ? "true" : "false",
      title: k.aciklama || k.ad,
      onclick: tiklanabilir ? () => katDegistir(kod) : null,
    }, k.ad);
  }

  function maddeKarti(m) {
    const kat = m.kategoriler || [];
    const ilk = kat.map((k) => durum.katHarita.get(k)).find(Boolean);
    const oneCikan = kat.some((k) => durum.vurgulu.has(k));
    return h("article", { class: "madde" + (oneCikan ? " one-cikan" : ""), style: ilk ? `--renk:${ilk.renk}` : null },
      h("div", { class: "madde-ust" },
        h("span", { class: "rozet" }, m.tur_kisa || "Diğer"),
        m.mukerrer ? h("span", { class: "rozet muk" }, `${m.mukerrer}. Mükerrer`) : null,
        m.kurum ? h("span", {}, m.kurum) : null,
        m.grup ? h("span", {}, m.grup) : null,
        h("span", { class: "bicim" }, m.bicim === "pdf" ? "PDF" : m.bicim === "htm" ? "Metin" : ""),
      ),
      h("a", { class: "madde-baslik", href: m.url, target: "_blank", rel: "noopener" }, m.baslik),
      kat.length ? h("div", { class: "madde-alt" }, kat.map((k) => katCip(k))) : null,
    );
  }

  function gunBasligi(tarih, maddeSayisi) {
    const sayilar = durum.sayiBilgisi.get(tarih) || [];
    return h("div", { class: "gun-baslik" },
      h("h3", {}, tarihYaz(tarih)),
      h("div", { class: "sayi" },
        sayilar.map((s) => h("span", {},
          s.mukerrer ? `${s.mukerrer}. Mükerrer ` : "Sayı ",
          h("b", {}, s.sayi),
          s.pdf ? [" · ", h("a", { href: s.pdf, target: "_blank", rel: "noopener" }, "PDF")] : null,
        )),
        h("span", {}, `${maddeSayisi} madde`),
      ),
    );
  }

  function ciz() {
    const sonuc = suz();
    const liste = $("#liste");
    liste.replaceChildren();
    const s = durum.suzgec;
    const filtreVar = s.q || s.t1 || s.t2 || s.tur || s.bolum || s.kat.size || s.yalnizVurgulu;

    if (!sonuc.length) {
      liste.append(h("div", { class: "bos-sonuc" },
        h("p", {}, "Bu filtrelerle eşleşen madde bulunamadı."),
        filtreVar ? h("button", { class: "dugme", type: "button", onclick: sifirla }, "Filtreleri temizle") : null));
    }

    const gosterilen = sonuc.slice(0, durum.limit);
    const gunSayac = new Map();
    for (const m of sonuc) gunSayac.set(m.tarih, (gunSayac.get(m.tarih) || 0) + 1);
    let gunKutusu = null;
    let sonTarih = null;
    for (const m of gosterilen) {
      if (m.tarih !== sonTarih) {
        sonTarih = m.tarih;
        gunKutusu = h("section", { class: "gun" }, gunBasligi(m.tarih, gunSayac.get(m.tarih)));
        liste.append(gunKutusu);
      }
      gunKutusu.append(maddeKarti(m));
    }

    const tarihler = [...gunSayac.keys()];
    const aralik = tarihler.length
      ? ` · ${tarihYaz(tarihler[tarihler.length - 1], kisaTarih)} – ${tarihYaz(tarihler[0], kisaTarih)}`
      : "";
    $("#sonuc-ozet").textContent = `${sayiBicim.format(sonuc.length)} madde${aralik}` +
      (sonuc.length > gosterilen.length ? ` · ilk ${sayiBicim.format(gosterilen.length)} gösteriliyor` : "");
    $("#daha").hidden = sonuc.length <= durum.limit;
    cipleriCiz();
  }

  function cipleriCiz() {
    const kutu = $("#kategoriler");
    const adet = new Map();
    for (const m of durum.maddeler) for (const k of m.kategoriler || []) adet.set(k, (adet.get(k) || 0) + 1);
    kutu.replaceChildren(...durum.kategoriler.map((k) => {
      const cip = katCip(k.kod);
      cip.append(h("span", { class: "adet" }, sayiBicim.format(adet.get(k.kod) || 0)));
      return cip;
    }));
  }

  function secenekleriDoldur() {
    const turler = new Map();
    const bolumler = new Set();
    for (const m of durum.maddeler) {
      turler.set(m.tur_kisa, (turler.get(m.tur_kisa) || 0) + 1);
      if (m.bolum) bolumler.add(m.bolum);
    }
    const turSec = $("#tur");
    const secili = durum.suzgec.tur;
    turSec.replaceChildren(h("option", { value: "" }, "Tümü"),
      ...[...turler.entries()].sort((a, b) => b[1] - a[1])
        .map(([t, n]) => h("option", { value: t }, `${t} (${sayiBicim.format(n)})`)));
    turSec.value = secili;
    const bolumSec = $("#bolum");
    const seciliB = durum.suzgec.bolum;
    bolumSec.replaceChildren(h("option", { value: "" }, "Tümü"),
      ...[...bolumler].map((b) => h("option", { value: b }, b.replace(/\s*BÖLÜMÜ$/i, "").toLocaleLowerCase("tr-TR").replace(/^\p{L}|\s\p{L}/gu, (c) => c.toLocaleUpperCase("tr-TR")))));
    bolumSec.value = seciliB;
  }

  function sonSayiCiz() {
    const kutu = $("#son-sayi");
    const g = durum.index && durum.index.gunler[0];
    if (!g) { kutu.replaceChildren(h("p", { class: "silik" }, "Henüz veri yok.")); return; }
    const sayilar = durum.sayiBilgisi.get(g.tarih) || [];
    const asil = sayilar.find((s) => !s.mukerrer) || sayilar[0] || {};
    const mukerrerAdet = sayilar.filter((s) => s.mukerrer).length;
    const vurguluAdet = Object.entries(g.kategoriler || {})
      .filter(([k]) => durum.vurgulu.has(k)).reduce((t, [, n]) => t + n, 0);
    kutu.replaceChildren(
      h("div", { class: "etiket" }, "Son sayı"),
      h("div", { class: "tarih" }, tarihYaz(g.tarih)),
      h("div", { class: "sayi" }, `Sayı ${asil.sayi || "—"}` + (mukerrerAdet ? ` · ${mukerrerAdet} mükerrer` : "")),
      h("div", { class: "rakamlar" },
        h("div", {}, h("b", {}, g.madde_sayisi), h("span", {}, "madde")),
        h("div", {}, h("b", {}, vurguluAdet), h("span", {}, "gümrük / dış ticaret")),
        h("div", {}, h("b", {}, sayiBicim.format(durum.index.gun_sayisi)), h("span", {}, "gün arşivde")),
      ),
      h("div", { class: "eylemler" },
        asil.pdf ? h("a", { class: "dugme birincil", href: asil.pdf, target: "_blank", rel: "noopener" }, "Gazetenin PDF'i") : null,
        h("a", { class: "dugme", href: VURGULU_AKIS }, "Gümrük RSS"),
      ),
    );
    $("#guncelleme").textContent = `Son veri: ${tarihYaz(g.tarih, kisaTarih)}`;
  }

  function vurguluCiz() {
    const g = durum.index && durum.index.gunler[0];
    if (!g) return;
    const maddeler = durum.maddeler.filter((m) => m.tarih === g.tarih && (m.kategoriler || []).some((k) => durum.vurgulu.has(k)));
    const liste = $("#vurgulu-liste");
    liste.replaceChildren(...(maddeler.length
      ? maddeler.map((m) => h("li", {},
          h("span", { class: "rozet" }, m.tur_kisa),
          h("a", { href: m.url, target: "_blank", rel: "noopener" }, m.baslik)))
      : [h("li", { class: "bos" }, "Son sayıda gümrük veya dış ticaretle ilgili madde yok. Son 90 gün için aşağıdaki “Yalnız gümrük ve dış ticaret” seçeneğini kullanın.")]));
    $("#vurgulu").hidden = false;
  }

  function rssCiz() {
    const liste = $("#rss-liste");
    const satir = (ad, yol, renk) => h("li", {},
      h("span", { class: "rss-ad" }, renk ? h("span", { class: "nokta", style: `background:${renk};box-shadow:none` }) : null, h("a", { href: yol }, ad)),
      h("button", { class: "kucuk-dugme", type: "button", onclick: (e) => kopyala(new URL(yol, location.href).href, e.currentTarget) }, "Adresi kopyala"));
    liste.replaceChildren(
      satir("Tüm maddeler", "feed.xml"),
      satir("Gümrük ve Dış Ticaret", VURGULU_AKIS, "var(--vurgu)"),
      ...durum.kategoriler.map((k) => satir(k.ad, `feeds/${k.kod}.xml`, k.renk)),
    );
  }

  async function kopyala(metin, dugme) {
    try {
      await navigator.clipboard.writeText(metin);
      const eski = dugme.textContent;
      dugme.textContent = "Kopyalandı";
      setTimeout(() => { dugme.textContent = eski; }, 1400);
    } catch { prompt("Adres:", metin); }
  }

  // ---------- olaylar ----------
  let zamanlayici = null;
  function degisti(hemen = false) {
    durum.limit = SAYFA;
    hashYaz();
    clearTimeout(zamanlayici);
    const calis = async () => { await eksikGunleriYukle(); ciz(); };
    if (hemen) calis(); else zamanlayici = setTimeout(calis, 140);
  }

  function katDegistir(kod) {
    const s = durum.suzgec.kat;
    if (s.has(kod)) s.delete(kod); else s.add(kod);
    degisti(true);
  }

  function sifirla() {
    durum.suzgec = { q: "", t1: "", t2: "", tur: "", bolum: "", kat: new Set(), yalnizVurgulu: false };
    formuDoldur();
    degisti(true);
  }

  function olaylariBagla() {
    $("#q").addEventListener("input", (e) => { durum.suzgec.q = e.target.value; degisti(); });
    $("#t1").addEventListener("change", (e) => { durum.suzgec.t1 = e.target.value; degisti(true); });
    $("#t2").addEventListener("change", (e) => { durum.suzgec.t2 = e.target.value; degisti(true); });
    $("#tur").addEventListener("change", (e) => { durum.suzgec.tur = e.target.value; degisti(true); });
    $("#bolum").addEventListener("change", (e) => { durum.suzgec.bolum = e.target.value; degisti(true); });
    $("#yalniz-vurgulu").addEventListener("change", (e) => { durum.suzgec.yalnizVurgulu = e.target.checked; degisti(true); });
    $("#sifirla").addEventListener("click", sifirla);
    $("#daha").addEventListener("click", () => { durum.limit += SAYFA; ciz(); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); $("#q").focus(); }
    });
    window.addEventListener("hashchange", () => { hashOku(); formuDoldur(); degisti(true); });
  }

  // ---------- başlat ----------
  async function basla() {
    temaKur();
    hashOku();
    try {
      const [index, kategoriler, son] = await Promise.all([
        jsonAl("data/index.json"), jsonAl("data/kategoriler.json"), jsonAl("data/son90.json"),
      ]);
      durum.index = index;
      durum.kategoriler = kategoriler;
      for (const k of kategoriler) {
        durum.katHarita.set(k.kod, k);
        if (k.vurgulu) durum.vurgulu.add(k.kod);
      }
      for (const m of son.maddeler) durum.maddeler.push(hazirla(m));
      for (const g of index.gunler) if (g.tarih >= son.baslangic) durum.yuklenenGunler.add(g.tarih);
      for (const g of index.gunler) durum.sayiBilgisi.set(g.tarih, g.sayilar);
      sirala();
      secenekleriDoldur();
      formuDoldur();
      sonSayiCiz();
      vurguluCiz();
      rssCiz();
      olaylariBagla();
      await eksikGunleriYukle();
      ciz();
    } catch (hata) {
      console.error(hata);
      $("#liste").replaceChildren(h("div", { class: "bos-sonuc" }, "Veri yüklenemedi. Sayfayı yenilemeyi deneyin."));
      $("#son-sayi").replaceChildren(h("p", { class: "silik" }, "Veri yüklenemedi."));
    }
  }

  basla();
})();
