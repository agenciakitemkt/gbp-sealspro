const test = require("node:test");
const assert = require("node:assert/strict");
const { pickCid, fromHref, mapsUrl } = require("../src/lib/cid.js");

const CID = "1311862289879068560"; // 0x1234abcd5678ef90

test("le ludocid, cid e o ftid dos links do Maps", () => {
  assert.deepEqual(fromHref(`/search?q=x&ludocid=${CID}&lsig=AB`), [CID]);
  assert.deepEqual(fromHref(`https://maps.google.com/maps?cid=${CID}`), [CID]);
  assert.deepEqual(fromHref("https://www.google.com/maps/place/x/data=!4m2!3m1!1s0x1a2b3c:0x1234abcd5678ef90"), [CID]);
  assert.deepEqual(fromHref(`/url?q=https%3A%2F%2Fmaps.google.com%2F%3Fcid%3D${CID}`), [CID]);
});

test("fica o CID que mais se repete (o do proprio negocio)", () => {
  const hrefs = [`/search?ludocid=${CID}`, `/search?ludocid=${CID}&x=1`, "/search?ludocid=11111111111", "/maps?cid=22222222222"];
  assert.equal(pickCid(hrefs), CID);
  assert.equal(pickCid(["/search?q=sem-cid"], [CID]), CID); // data-ludocid
});

test("sem CID valido: null (e o botao nao aparece)", () => {
  assert.equal(pickCid([]), null);
  assert.equal(pickCid(["/search?q=x", "javascript:alert(1)", "/search?ludocid=abc", "/search?ludocid=0"]), null);
  assert.equal(pickCid([], ["<script>", "12"]), null);
});

test("URL do Maps so com CID numerico", () => {
  assert.equal(mapsUrl(CID), `https://www.google.com/maps?cid=${CID}&hl=pt-BR`);
  for (const bad of ["12&q=x", "javascript:1", "", null, "1".repeat(30)]) assert.equal(mapsUrl(bad), null, String(bad));
});
