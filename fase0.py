#!/usr/bin/env python3
"""Fase 0: verificar acesso ao Google Business Profile.

  python3 fase0.py login                 # OAuth (business.manage), grava o refresh token
  python3 fase0.py listar                # contas e locais que voce administra
  python3 fase0.py local <nome|locations/ID> [--raw]   # campos da secao 6 do CLAUDE.md
"""

import argparse
import json
import sys

import gbp_auth as g

READ_MASK = ("name,title,storefrontAddress,phoneNumbers,categories,websiteUri,regularHours,"
             "specialHours,profile,serviceItems,openInfo,metadata,latlng")


def listar_locais(conta):
    return g.paginate("info", f"{conta}/locations", "locations",
                      {"readMask": "name,title,storefrontAddress", "pageSize": 100}, soft=True)


def todos_locais():
    contas = g.paginate("accounts", "accounts", "accounts")
    return [(c, listar_locais(c["name"])) for c in contas]


def cmd_listar(_):
    for conta, locais in todos_locais():
        print(f"{conta['name']}  {conta.get('accountName', '')}  [{conta.get('type', '')}]")
        if isinstance(locais, dict):
            print(f"   erro: {locais['_erro']}")
            continue
        for loc in locais:
            cidade = loc.get("storefrontAddress", {}).get("locality", "")
            print(f"   {loc['name']}  {loc.get('title', '')}  {cidade}")
    print("\nContas acessiveis OK.")


def achar_local(alvo):
    """Devolve (account, location_id). Aceita locations/ID ou parte do nome."""
    for conta, locais in todos_locais():
        if isinstance(locais, dict):
            continue
        for loc in locais:
            if alvo == loc["name"] or alvo.lower() in loc.get("title", "").lower():
                return conta["name"], loc["name"]
    sys.exit(f"Local '{alvo}' nao encontrado. Rode 'listar'.")


def secao(titulo, dado):
    print(f"\n=== {titulo} ===")
    if isinstance(dado, dict) and "_erro" in dado:
        print(f"  ERRO: {dado['_erro']}")
    else:
        print(json.dumps(dado, indent=2, ensure_ascii=False))


def resumo_midia(itens):
    """Midia v4: so os campos que a analise usa (formato, categoria, origem, data)."""
    return [{"formato": m.get("mediaFormat"),
             "categoria": m.get("locationAssociation", {}).get("category"),
             "criadoEm": m.get("createTime")} for m in itens]


def cmd_local(args):
    conta, loc = achar_local(args.alvo)
    v4 = f"{conta}/{loc}"
    info = g.get("info", loc, {"readMask": READ_MASK})
    reviews = g.paginate("v4", f"{v4}/reviews", "reviews", {"pageSize": 50}, soft=True)
    resumo = g.get("v4", f"{v4}/reviews", {"pageSize": 1}, soft=True)
    midia = g.paginate("v4", f"{v4}/media", "mediaItems", {"pageSize": 100}, soft=True)
    midia_cli = g.paginate("v4", f"{v4}/media/customers", "mediaItems", {"pageSize": 100}, soft=True)
    posts = g.paginate("v4", f"{v4}/localPosts", "localPosts", {"pageSize": 100}, soft=True)

    if args.raw:
        print(json.dumps({"info": info, "reviews": reviews, "resumoReviews": resumo, "midia": midia,
                          "midiaClientes": midia_cli, "posts": posts}, indent=2, ensure_ascii=False))
        return

    print(f"Local: {info.get('title')}  ({loc})")
    secao("Telefone (phoneNumbers)", info.get("phoneNumbers"))
    secao("Site (websiteUri)", info.get("websiteUri"))
    secao("Descricao (profile.description)", info.get("profile"))
    cats = info.get("categories", {})
    secao("Categorias", {"principal": cats.get("primaryCategory", {}).get("displayName"),
                         "adicionais": [c.get("displayName") for c in cats.get("additionalCategories", [])]})
    secao("Endereco (storefrontAddress)", info.get("storefrontAddress"))
    secao("Horario normal (regularHours)", info.get("regularHours"))
    secao("Horario especial (specialHours)", info.get("specialHours"))
    servicos = info.get("serviceItems", [])
    secao("Servicos (serviceItems)", {"total": len(servicos), "exemplos": [
        (i.get("freeFormServiceItem") or i.get("structuredServiceItem") or {}).get("label", {}).get("displayName")
        or i.get("structuredServiceItem", {}).get("serviceTypeId") for i in servicos[:5]]})
    secao("Data de abertura/fundacao (openInfo)", info.get("openInfo"))
    secao("Links (metadata)", info.get("metadata"))

    if isinstance(reviews, dict):
        secao("Avaliacoes (v4)", reviews)
    else:
        print("\n=== Avaliacoes (v4) ===")
        print(f"  nota media: {resumo.get('averageRating')}  total: {resumo.get('totalReviewCount')}  "
              f"baixadas: {len(reviews)}")
        dist = {}
        for r in reviews:
            dist[r.get("starRating")] = dist.get(r.get("starRating"), 0) + 1
        print(f"  distribuicao: {dist}")
        print(f"  sem resposta: {sum(1 for r in reviews if 'reviewReply' not in r)}  "
              f"sem comentario: {sum(1 for r in reviews if not r.get('comment'))}")
        if reviews:
            print("  mais recente:", json.dumps({k: reviews[0].get(k) for k in
                  ("starRating", "createTime", "comment", "reviewReply")}, ensure_ascii=False))
    secao("Midia do proprietario (v4)", midia if isinstance(midia, dict) else resumo_midia(midia))
    secao("Midia de clientes (v4)", midia_cli if isinstance(midia_cli, dict) else resumo_midia(midia_cli))
    if isinstance(posts, dict):
        secao("Postagens (v4)", posts)
    else:
        secao("Postagens (v4): datas", [{"tipo": p.get("topicType"), "criadoEm": p.get("createTime")} for p in posts])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login").set_defaults(fn=lambda _: g.login())
    sub.add_parser("listar").set_defaults(fn=cmd_listar)
    loc = sub.add_parser("local")
    loc.add_argument("alvo", help="locations/ID ou parte do nome")
    loc.add_argument("--raw", action="store_true", help="JSON bruto completo")
    loc.set_defaults(fn=cmd_local)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
