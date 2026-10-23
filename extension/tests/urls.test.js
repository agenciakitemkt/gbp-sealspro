const test = require("node:test");
const assert = require("node:assert/strict");
const { placeInfo, searchUrl, galleryUrl } = require("../src/lib/urls.js");

const PLACE = "https://www.google.com/maps/place/Neg%C3%B3cio+Exemplo/@-19.9010000,-43.9010000,16.36z/data=!4m6!3m5!1s0x1a2b3c:0x1234abcd5678ef90!8m2!3d-19.9012345!4d-43.9012345!16s%2Fg%2F11exemplo?hl=pt-BR&entry=ttu";

test("galeria por categoria: insere !10e5!14m1!1B<codigo> e ajusta as contagens", () => {
  const url = galleryUrl(PLACE, "CgIgARICEAE=");
  // mesmo bloco de uma URL real do Maps: codigo sem o "=" final
  assert.ok(url.includes("!4m9!3m8!1s0x1a2b3c:0x1234abcd5678ef90!8m2!3d-19.9012345!4d-43.9012345!10e5!14m1!1BCgIgARICEAE!16s"), url);
  assert.ok(galleryUrl(PLACE, "CgIgARICCAQ=").includes("!14m1!1BCgIgARICCAQ!16s"));
  assert.ok(galleryUrl(PLACE, "Cg+a/b==").includes("!1BCg%2Ba%2Fb!16s"));
  assert.ok(url.endsWith("?hl=pt-BR"));
  assert.ok(url.startsWith("https://www.google.com/maps/place/"));
});

test("galeria: endereco fora do formato ou codigo estranho = null", () => {
  assert.equal(galleryUrl("https://www.google.com/maps/search/x", "CgIgARICEAE="), null);
  assert.equal(galleryUrl("https://evil.example/maps/place/x/data=!4m6!3m5!1s0x1:0x2!8m2!3d1!4d2", "CgIgARICEAE="), null);
  assert.equal(galleryUrl(PLACE, "Cg<script>"), null);
  assert.equal(galleryUrl(PLACE, ""), null);
  assert.equal(galleryUrl(galleryUrl(PLACE, "CgIgARICEAE="), "CgIgARICCAQ="), null); // ja e galeria
});

test("busca dos concorrentes", () => {
  assert.equal(searchUrl("Agência de marketing digital", -19.9012345, -43.9012345),
    "https://www.google.com/maps/search/Ag%C3%AAncia+de+marketing+digital/@-19.9012345,-43.9012345,13z?hl=pt-BR");
  assert.equal(searchUrl("", 1, 2), null);
  assert.equal(searchUrl("x", 91, 2), null);
  assert.equal(searchUrl("x".repeat(101), 1, 2), null);
  assert.ok(searchUrl("a/b?c#d", 1, 2).includes("/search/a%2Fb%3Fc%23d/@"));
});

test("leitura minima da fonte A", () => {
  const p = []; p[9] = [null, null, -19.94, -43.96]; p[13] = ["Faz-tudo"];
  p[171] = [[["CgIgAQ==", 0, "Tudo"], ["CgIgARICEAE=", 0, "From the owner"], ["<x>", 0, "lixo"]]];
  const text = ")]}'\n" + JSON.stringify([null, null, null, null, null, null, p]);
  assert.deepEqual(placeInfo(text), { category: "Faz-tudo", lat: -19.94, lng: -43.96, codes: ["CgIgAQ==", "CgIgARICEAE="], city: null, uf: null });
  assert.equal(placeInfo("lixo"), null);
  assert.equal(placeInfo(null), null);
});

test("dados do perfil aberto: so a preview/place com o mesmo identificador da URL", () => {
  const { placeForProfile, ftidFromUrl, ftidFromPlace } = require("../src/lib/urls.js");
  const place = (ftid, name) => { const p = []; p[10] = ftid; p[11] = name; return ")]}'\n" + JSON.stringify([0, 0, 0, 0, 0, 0, p]); };
  const mine = place("0x1a2b3c:0x1234abcd5678ef90", "Negocio");
  const other = place("0xaa:0xbb", "Clube do mapa");
  assert.equal(ftidFromUrl(PLACE), "0x1a2b3c:0x1234abcd5678ef90");
  assert.equal(ftidFromPlace(mine), "0x1a2b3c:0x1234abcd5678ef90");
  assert.equal(placeForProfile([mine, other], PLACE), mine);     // o mais recente (outro local) e ignorado
  assert.equal(placeForProfile([other], PLACE), null);
  assert.equal(placeForProfile([mine], "https://www.google.com/maps?cid=1"), null); // sem perfil na URL
  assert.equal(ftidFromPlace("lixo"), null);
});

test("categoria da pagina da galeria: [13][0]; visualizador do Street View (sem [13]) e lixo = null", () => {
  const { galleryCategory } = require("../src/lib/urls.js");
  const wrb = (inner) => `)]}'\n\n123\n${JSON.stringify([["wrb.fr", "hspqX", JSON.stringify(inner)]])}\n`;
  const page = [[], 2, null, "x", null, "y", null, null, null, null, true, null, [], ["CgIgARICCAI="]];
  assert.equal(galleryCategory(wrb(page)), "CgIgARICCAI=");
  assert.equal(galleryCategory(wrb(page.slice(0, 11))), null);
  for (const junk of [null, "", "lixo", ")]}'\n[\"wrb.fr\"", wrb({ a: 1 })]) assert.equal(galleryCategory(junk), null);
});

test("galeria: estado de outro painel (avaliacoes abertas, !9m1!1b1) nao vai junto", () => {
  const afterReviews = "https://www.google.com/maps/place/X/@-19.96,-44.03,17z/data=!4m8!3m7!1s0x1a2b3c:0x1234abcd5678ef90!8m2!3d-19.9600000!4d-44.0300000!9m1!1b1!16s%2Fg%2F11exemplo?hl=pt-BR&entry=ttu";
  assert.equal(galleryUrl(afterReviews, "CgIgARICCAI="),
    "https://www.google.com/maps/place/X/@-19.96,-44.03,17z/data=!4m9!3m8!1s0x1a2b3c:0x1234abcd5678ef90!8m2!3d-19.9600000!4d-44.0300000!10e5!14m1!1BCgIgARICCAI!16s%2Fg%2F11exemplo?hl=pt-BR");
  const prefixed = "https://www.google.com/maps/place/X/@1,2,17z/data=!3m1!4b1!4m6!3m5!1s0x1:0x2!8m2!3d1.5!4d2.5!16s%2Fg%2Fx";
  assert.equal(galleryUrl(prefixed, "CgIgAQ=="),
    "https://www.google.com/maps/place/X/@1,2,17z/data=!3m1!4b1!4m9!3m8!1s0x1:0x2!8m2!3d1.5!4d2.5!10e5!14m1!1BCgIgAQ!16s%2Fg%2Fx?hl=pt-BR");
  const noId = "https://www.google.com/maps/place/X/data=!4m5!3m4!1s0x1:0x2!8m2!3d1!4d2";
  assert.ok(galleryUrl(noId, "CgIgAQ==").endsWith("data=!4m8!3m7!1s0x1:0x2!8m2!3d1!4d2!10e5!14m1!1BCgIgAQ?hl=pt-BR"));
});

test("fim da categoria da galeria: true em [10]", () => {
  const { galleryEnd } = require("../src/lib/urls.js");
  const wrb = (inner) => `)]}'\n\n123\n${JSON.stringify([["wrb.fr", "hspqX", JSON.stringify(inner)]])}\n`;
  const page = (end) => [[], 4, null, "x", null, "y", null, null, null, null, end, null, [], ["CgIgARICCAQ="]];
  assert.equal(galleryEnd(wrb(page(true))), true);
  assert.equal(galleryEnd(wrb(page(false))), false);
  assert.equal(galleryEnd("lixo"), false);
});

test("busca dos concorrentes como no GBP Check: categoria, cidade e estado por extenso", () => {
  assert.equal(searchUrl("Oftalmologista", -23.1012345, -45.8012345, "São José dos Campos", "SP"),
    "https://www.google.com/maps/search/Oftalmologista+S%C3%A3o+Jos%C3%A9+dos+Campos-S%C3%A3o+Paulo/@-23.1012345,-45.8012345,13z?hl=pt-BR");
  // UF desconhecida ou cidade estranha: so a categoria
  assert.ok(searchUrl("Imobiliária", 1, 2, "Belo Horizonte", "XX").includes("/search/Imobili%C3%A1ria/@"));
  assert.ok(searchUrl("Imobiliária", 1, 2, "<script>", "MG").includes("/search/Imobili%C3%A1ria/@"));
  const info = placeInfo(JSON.stringify(Object.assign([], { 6: Object.assign([], { 2: ["Rua X, 1 - Centro", "Belo Horizonte - MG", "30180-060"], 9: [0, 0, -19.92, -43.95], 13: ["Imobiliária"] }) })));
  assert.equal(info.city, "Belo Horizonte");
  assert.equal(info.uf, "MG");
});
