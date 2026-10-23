"""Comparacao ao vivo da Pre Analise: GBP Check x nossa, no mesmo perfil e no mesmo dia (CLAUDE.md, 12.9 fase 4).

  ./.venv/bin/python comparar_pre_ao_vivo.py add <resposta_gbp.json> <referencia.json>
      Converte a resposta do GBP Check (corpo do POST /extension-v2/healthcheck da pagina de resultado da Pre Analise)
      para o formato de pre_analises_original.json e acrescenta ao arquivo (o mais recente de cada perfil vale).
  ./.venv/bin/python comparar_pre_ao_vivo.py compare <referencia.json> <cid> <id da nossa pre analise>
      Dados (perfil normalizado) e notas lado a lado: GBP Check | nosso motor com os dados do GBP | nossa captura
      reavaliada com o motor atual, em memoria (nada e gravado). "<-- regra" = o motor erra; "<-- dados" = a coleta difere.
"""
import json
import os
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collector_pre.from_original import to_profile  # noqa: E402
from collector_pre.maps_reader import read_capture  # noqa: E402
from scoring.pre import analyze  # noqa: E402


def uuid7():
    ms = int(time.time() * 1000)
    rand = uuid.uuid4().int & ((1 << 80) - 1)
    value = (ms << 80) | (0x7 << 76) | (rand & ((1 << 76) - 1))
    value = (value & ~(0xC << 60)) | (0x8 << 60)  # variante
    return str(uuid.UUID(int=value))


def add(src, dest):
    raw = json.load(open(src))
    d = json.loads(raw) if isinstance(raw, str) else raw
    r = d["pre_health_check_result"]
    case = {"id": uuid7(), "stats": r["statistics"], "basic": r["basic_info"],
            "items": [{"id": i["id"], "t": i.get("title"), "s": i["score"], "st": i.get("status")} for i in r["items"]],
            "pd": d["profile_data"], "ncomp": d["profile_data"].get("competitors_considered_count"),
            "competitors": d.get("result_competitors_data")}
    cases = json.load(open(dest)) if os.path.exists(dest) else []
    cases = [c for c in cases if c["pd"].get("cid") != case["pd"].get("cid")]  # o mais recente do perfil vale
    cases.append(case)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    print(f"{case['basic']['location_name']}: cid {case['pd'].get('cid')}, nota {case['stats']['overall_score']}; "
          f"{len(cases)} casos em {dest}")


def flat(p):
    rv, md, ps, cp, loc = p["reviews"], p.get("media") or {}, p.get("posts") or {}, p.get("competitors") or {}, p["location"]
    s = rv.get("sample") or {}
    return {
        "avaliacoes: total": rv.get("count"), "avaliacoes: media": rv.get("average"),
        "avaliacoes: estrelas 5-1": rv.get("starDistribution"), "ultima avaliacao (dias)": rv.get("lastReviewDays"),
        "amostra: tamanho": s.get("size"), "amostra: sem resposta": s.get("unanswered"),
        "amostra: com texto": s.get("withText"), "amostra: media": s.get("average"),
        "ultima foto do dono (dias)": md.get("lastOwnerPhotoDays"), "videos": md.get("videos"),
        "fotos 360": md.get("photos360"), "postagens": ps.get("count"), "ultima postagem (dias)": ps.get("lastPostDays"),
        "concorrentes": cp.get("count"), "media do segmento": cp.get("averageReviews"),
        "top 10": cp.get("inTop10ByReviews"), "redes sociais": len(loc.get("socialLinks") or []),
        "descricao (caracteres)": len(loc.get("description") or ""), "nome (caracteres)": len(loc.get("name") or ""),
        "site": loc.get("website"), "verificado": loc.get("verified"), "telefone": bool(loc.get("phone")),
        "logo": bool(loc.get("logoUrl")), "horario": bool(loc.get("hours")),
    }


def compare(ref_path, cid, pre_id):
    case = next(c for c in json.load(open(ref_path)) if str(c["pd"].get("cid")) == str(cid))
    db = sqlite3.connect("data/gbp.db")
    raw_path, stored = db.execute("SELECT raw_path, result FROM pre_analyses WHERE id=?", (pre_id,)).fetchone()
    ours_p = read_capture(json.load(open(raw_path)))
    theirs_p = to_profile(case)
    print(f"== {case['basic']['location_name']} (GBP Check x nossa pre analise {pre_id})\n")
    print("DADOS")
    a, b = flat(theirs_p), flat(ours_p)
    for k in a:
        mark = "" if a[k] == b[k] else "   <-- diferente"
        print(f"  {k:28} GBP: {str(a[k])[:40]:42} nossa: {str(b[k])[:40]}{mark}")
    print("\nNOTAS (GBP Check | nosso motor com os dados do GBP | nossa analise)")
    on_theirs = {i["originalId"]: i for i in analyze(theirs_p)["items"]}
    recomputed = analyze(ours_p)  # motor atual, em memoria (nada e gravado)
    ours = {i["originalId"]: i for i in recomputed["items"]}
    for it in case["items"]:
        x, y, z = it["s"], on_theirs[it["id"]]["score"], ours[it["id"]]["score"]
        flag = "" if x == y == z else ("   <-- regra" if x != y else "   <-- dados")
        print(f"  {it['id']:26} {str(x):>5} {str(y):>5} {str(z):>5}{flag}")
    st = case["stats"]
    r = recomputed
    print(f"\nGERAL  GBP: {st['overall_score']} ({st['good_items']}/{st['fair_items']}/{st['bad_items']})  "
          f"nossa: {r['overall']['score']} ({r['overall']['good']}/{r['overall']['fair']}/{r['overall']['bad']})")


if __name__ == "__main__":
    {"add": add, "compare": compare}[sys.argv[1]](*sys.argv[2:])
