const test = require("node:test");
const assert = require("node:assert/strict");
const { pageUrl, nextToken, ftidFor, collect, PATH, SORT } = require("../src/lib/reviews-search.js");

const FTID = "0x1a2b3c4d5e6f70:0x1122334455667788";
const page = (token, n = 10) => `)]}'\n\n${JSON.stringify([[null], [null, null, null, null, null, null, null, null, null, null,
  [null, null, Array.from({ length: n }, (_, i) => [null, 5, ["x", null, String(i)]]), null, null, null, token]]])}`;

test("pedido de pagina: so o caminho da caixa de avaliacoes, em en-BR, com ftid e token validos", () => {
  const url = pageUrl(FTID, SORT.lowest, null);
  assert.ok(url.startsWith(PATH + "?hl=en-BR&reqpld="));
  const pld = JSON.parse(decodeURIComponent(url.split("reqpld=")[1].split("&")[0]));
  assert.equal(pld[1][9][1], 4);
  assert.deepEqual(pld[1][9][11], [FTID]);
  assert.equal(pld[1][9][19], null);
  assert.equal(JSON.parse(decodeURIComponent(pageUrl(FTID, SORT.newest, "abc_-1").split("reqpld=")[1].split("&")[0]))[1][9][19], "abc_-1");
  assert.equal(pageUrl("0x1:<x>", 4, null), null);
  assert.equal(pageUrl(FTID, 9, null), null);
  assert.equal(pageUrl(FTID, 4, 'a"b'), null);
});

test("token da proxima pagina; vazio ou lixo = fim", () => {
  assert.equal(nextToken(page("TOK")), "TOK");
  assert.equal(nextToken(page("")), null);
  assert.equal(nextToken("lixo"), null);
});

test("ftid do negocio pelos links do painel, conferido com o CID", () => {
  const cid = BigInt("0x1122334455667788").toString();
  assert.equal(ftidFor(["/maps?x", "https://maps.google.com/?q=a&ftid=0x1:0x2", `/maps/place/x/data=!4m2!3m1!1s${FTID}`], cid), FTID);
  assert.equal(ftidFor(["https://x/0x1:0x2"], cid), null);
});

test("coleta: menor nota e mais recentes, ate 5 paginas cada, parando no fim ou em erro", async () => {
  const calls = [];
  const fetchText = async (url) => {
    calls.push(url);
    const pld = JSON.parse(decodeURIComponent(url.split("reqpld=")[1].split("&")[0]));
    const sort = pld[1][9][1];
    if (sort === SORT.lowest) return page(calls.length < 3 ? "T" + calls.length : ""); // 3 paginas
    return page("T");                                                                  // sem fim: para em 13
  };
  let pauses = 0;
  const out = await collect(FTID, fetchText, async () => { pauses++; });
  assert.equal(out.lowest.length, 3);
  assert.equal(out.newest.length, 13);
  assert.equal(pauses, 16);
  const failing = await collect(FTID, async () => { throw new Error("x"); }, async () => {});
  assert.deepEqual(failing, { lowest: [], newest: [] });
  const junk = await collect(FTID, async () => "<html>", async () => {});
  assert.deepEqual(junk, { lowest: [], newest: [] });
});
