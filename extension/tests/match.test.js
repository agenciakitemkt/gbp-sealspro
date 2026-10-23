const test = require("node:test");
const assert = require("node:assert/strict");
const { classify } = require("../src/lib/match.js");

test("reconhece so as quatro respostas do Maps", () => {
  assert.equal(classify("https://www.google.com/maps/preview/place?authuser=0&hl=pt-BR&pb=!1m1"), "place");
  assert.equal(classify("https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=qv9Egd&hl=pt-BR"), "reviews");
  assert.equal(classify("https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=hspqX"), "photos");
  assert.equal(classify("https://www.google.com/search?tbm=map&authuser=0&hl=pt-BR&q=faz-tudo"), "search");
  assert.equal(classify("/maps/preview/place?pb=1", "https://www.google.com/maps/place/x"), "place");
});

test("ignora qualquer outra coisa", () => {
  for (const url of [
    "https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=outro",
    "https://www.google.com/search?q=x",
    "http://www.google.com/maps/preview/place",
    "https://evil.example/maps/preview/place",
    "https://www.google.com.evil.example/maps/preview/place",
    "https://www.google.com.br/maps/preview/place",
    "nao e url ::::",
    "",
  ]) assert.equal(classify(url), null, url);
});
