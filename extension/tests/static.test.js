// Regras de seguranca conferidas no codigo-fonte: quem pode ver o segredo e falar com o app local.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
// Codigo sem comentarios: linhas //, blocos /* */ e comentario no fim da linha (" // ", que URL nao tem).
const code = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\s\/\/\s.*$/gm, "");
const read = (f) => code(fs.readFileSync(path.join(ROOT, f), "utf8"));
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "manifest.json"), "utf8"));
const [mainWorld, isolated, searchPage] = manifest.content_scripts;
const SW_ONLY = ["src/background.js", "src/lib/run.js"];

test("scripts do mundo MAIN nao tocam em chrome.*, segredo nem app local", () => {
  assert.equal(mainWorld.world, "MAIN");
  for (const f of mainWorld.js) {
    const src = read(f);
    for (const forbidden of ["chrome.", "sealsSecret", "X-Seals-Secret", "127.0.0.1", "storage"]) {
      assert.ok(!src.includes(forbidden), `${f} contem ${forbidden}`);
    }
  }
});

test("content scripts nao falam com o app local nem leem o segredo", () => {
  for (const f of [...mainWorld.js, ...isolated.js, ...searchPage.js]) {
    const src = read(f);
    for (const forbidden of ["sealsSecret", "X-Seals-Secret", "127.0.0.1", "chrome.storage"]) {
      assert.ok(!src.includes(forbidden), `${f} contem ${forbidden}`);
    }
    assert.ok(!SW_ONLY.includes(f), `${f} so pode rodar no service worker`);
  }
});

test("so o service worker e a pagina de opcoes conhecem o segredo e o endereco do app", () => {
  const files = fs.readdirSync(path.join(ROOT, "src"), { recursive: true }).filter((f) => f.endsWith(".js")).map((f) => path.join("src", f));
  for (const f of files) {
    const src = read(f);
    if (src.includes("sealsSecret")) assert.ok(["src/background.js", "src/options.js"].includes(f), f);
    if (src.includes("127.0.0.1")) assert.ok(["src/lib/run.js", "src/options.js"].includes(f), f); // opcoes: so texto de ajuda
    if (/\bfetch\b/.test(src)) assert.ok(["src/lib/run.js", "src/background.js", "src/lib/hook.js", "src/content.js", "src/search.js"].includes(f), f);
  }
  assert.ok(read("src/background.js").includes('importScripts("lib/cid.js", "lib/urls.js", "lib/ranking.js", "lib/run.js")'));
});

test("tirar comentarios nao esconde codigo", () => {
  assert.equal(code('const a = "http://127.0.0.1:8000"; // comentario'), 'const a = "http://127.0.0.1:8000";');
});

test("nenhum innerHTML, eval ou Function no codigo da extensao", () => {
  const files = fs.readdirSync(path.join(ROOT, "src"), { recursive: true }).filter((f) => f.endsWith(".js"));
  for (const f of files) {
    const src = read(path.join("src", f));
    for (const forbidden of ["innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function", "document.write"]) {
      assert.ok(!src.includes(forbidden), `${f} contem ${forbidden}`);
    }
  }
});

test("content.js so busca enderecos do proprio Google: preload reconhecido por classify ou o modelo da busca do Maps", () => {
  const src = read("src/content.js");
  const calls = (src.match(/\bfetch\(/g) || []).length;
  const preload = (src.match(/classify\(href\) === [^)]{1,20}\)[\s\S]{0,80}?fetch\(href, \{ credentials: "same-origin" \}\)/g) || []).length;
  // ranking (secao 16): so o endereco montado do modelo tbm=map da propria pagina, e sem cookies
  const ranking = (src.match(/if \(!isPointTemplate\(url\)\) return "";\s*const resp = await fetch\(url, \{ credentials: "omit" \}\)/g) || []).length;
  assert.ok(calls >= 2);
  assert.equal(preload + ranking, calls, "todo fetch do content script precisa vir depois de classify(href) ou isPointTemplate(url)");
  assert.equal(ranking, 1);
  // Google pedindo verificacao (captcha): a coleta para
  assert.ok(src.includes('if (resp.status === 429 || /\\/sorry\\//.test(resp.url || "")) throw new Error(BLOCKED);'));
});

test("mensagem externa: so do app local (manifest e conferencia no service worker)", () => {
  assert.deepEqual(manifest.externally_connectable, { matches: ["http://127.0.0.1:8000/*"] });
  const bg = read("src/background.js");
  assert.equal((bg.match(/onMessageExternal/g) || []).length, 1);
  assert.ok(bg.includes('msg.type !== "seals:ranking-run"'));
  assert.ok(read("src/lib/run.js").includes('!sender.url.startsWith(APP + "/")'));
});

test("ranking: o modelo do pedido so pode ser a busca tbm=map do proprio Google", () => {
  const src = read("src/lib/ranking.js");
  assert.ok(src.includes('const TEMPLATE_PREFIX = "https://www.google.com/search?tbm=map&";'));
  assert.ok(src.includes("href.startsWith(TEMPLATE_PREFIX)"));
  assert.ok(!/\bfetch\b/.test(src));
});

test("pagina de busca: so le links, mostra o botao e busca a amostra de avaliacoes; nao envia ao app", () => {
  const src = read("src/search.js");
  for (const forbidden of ["XMLHttpRequest", "postMessage", "__sealsHook", "seals:submit", "seals:begin", "127.0.0.1"]) {
    assert.ok(!src.includes(forbidden), forbidden);
  }
  // um unico fetch, na propria origem, para o caminho montado por reviews-search.js (pageUrl sempre comeca com PATH)
  assert.equal((src.match(/\bfetch\(/g) || []).length, 1);
  assert.ok(src.includes("fetch(location.origin + path, {"));
  assert.ok(src.includes("reviewsSearch.collect(ftid, fetchText,"));
  assert.ok(src.includes('type: "seals:open-maps"'));
  // so le o bloco "Perfis" pelo data-attrid (independe do idioma)
  assert.ok(src.includes('kc:/common/topic:social media presence'));
});

test("botao na pagina: shadow DOM fechado e so clique de verdade", () => {
  const src = read("src/lib/button.js");
  assert.match(src, /attachShadow\(\{ mode: "closed" \}\)/);
  assert.match(src, /isTrusted !== true/);
  assert.ok(!/position:\s*(fixed|absolute)/.test(src), "o botao fica em linha, sem cobrir nada");
});

test("nenhum arquivo em duas entradas que rodam na mesma pagina (o Chrome injetaria so uma vez)", () => {
  const [main, isolated] = manifest.content_scripts;
  assert.deepEqual(main.matches, isolated.matches);
  const shared = main.js.filter((f) => isolated.js.includes(f));
  assert.deepEqual(shared, []);
});

test("copia do match.js do mundo MAIN e identica a original", () => {
  const raw = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");
  assert.equal(raw("src/main/match.js"), raw("src/lib/match.js"));
});

test("dependencias de cada entrada vem antes de quem as usa", () => {
  const provides = { "__sealsMatch": /match\.js$/, "__sealsBuffer": /buffer\.js$/, "__sealsSteps": /steps\.js$/,
                     "__sealsSession": /session\.js$/, "__sealsButton": /button\.js$/, "__sealsHook": /hook\.js$/,
                     "__sealsCid": /cid\.js$/, "__sealsUrls": /urls\.js$/,
                     "__sealsRanking": /ranking\.js$/ };
  for (const cs of manifest.content_scripts) {
    cs.js.forEach((f, i) => {
      for (const [name, file] of Object.entries(provides)) {
        if (read(f).includes(`globalThis.${name}`) && !file.test(f)) {
          assert.ok(cs.js.slice(0, i).some((g) => file.test(g)), `${f} usa ${name} sem carregar antes`);
        }
      }
    });
  }
});
