"""Diagnostico da Analise Completa para outras ferramentas (por exemplo, uma skill do Claude que aplica as mudancas).

E o contrato entre os dois projetos: o gbp-sealspro MEDE (nota, itens, o que falta) e a skill AGE (briefing, plano e
escrita no perfil). A skill nunca reimplementa as regras: chama `coletar.py diagnostico` e le este JSON.

Mudar o formato quebra a skill. Por isso o JSON leva `contrato` (numero da versao do formato) e um teste trava os
campos. Ao mudar o formato: subir CONTRATO e atualizar a skill do outro lado.

Nunca entra texto de avaliacoes de clientes: das avaliacoes saem so contagens.
"""

import history
import storage
from report import texts
from report.build import _item_texts, is_current_version
from scoring import analyze

CONTRATO = 1

# Como cada item se resolve: "texto" (a agencia preenche um campo do perfil), "material" (precisa de foto, video ou
# logotipo do cliente), "postagem" (publicar no perfil), "resposta" (responder avaliacoes) ou "cliente" (depende de
# clientes do negocio: avaliacoes e fotos enviadas por eles; a agencia so gera a acao, como o link de avaliacao).
COMO_RESOLVER = {
    "phone": "texto", "website": "texto", "hours": "texto", "special_hours": "texto", "description": "texto",
    "services": "texto", "founding_date": "texto", "business_name": "texto",
    "logo": "material", "cover": "material", "videos": "material", "owner_media": "material",
    "total_media": "material", "last_owner_media": "material",
    "last_post": "postagem", "reviews_unanswered": "resposta",
    "customer_media": "cliente", "reviews_count": "cliente", "reviews_average": "cliente",
    "reviews_no_comment": "cliente", "reviews_trend": "cliente",
}
# Campo da Business Information API que o item altera, quando e um campo do perfil.
CAMPO_API = {
    "phone": "phoneNumbers", "website": "websiteUri", "hours": "regularHours", "special_hours": "specialHours",
    "description": "profile.description", "services": "serviceItems", "founding_date": "openInfo.openingDate",
    "business_name": "title",
}
# Mudar estes pode levar o Google a pedir nova verificacao ou suspender o perfil: so com confirmacao explicita.
CUIDADO = {"business_name": "Mudar o nome pode levar o Google a pedir nova verificação. Nunca acrescentar "
                            "palavras-chave ao nome: só o nome real da empresa."}


def _perfil(profile):
    loc = profile["location"]
    return {
        "nome": loc["name"], "categoria": loc["category"], "categoriasAdicionais": loc["additionalCategories"],
        "endereco": loc["address"], "cidade": loc["city"], "telefone": loc["phone"], "site": loc["website"],
        "descricao": loc["description"], "horario": loc["hours"], "horarioEspecial": loc["specialHours"],
        "servicos": loc["services"], "aceitaServicos": loc["servicesEditable"], "dataFundacao": loc["openingDate"],
        "mapsUrl": loc["mapsUrl"], "temLogotipo": bool(loc["logoUrl"]), "temCapa": bool(loc["coverUrl"]),
    }


def build(db, location_id, analysis=None):
    """Diagnostico da ultima analise real do local (ou de `analysis`). Recalcula com o motor atual a partir do bruto,
    em memoria, para o diagnostico seguir sempre as regras de hoje. LookupError se nao houver analise real."""
    analysis = analysis or storage.latest_analysis(db, location_id)
    if analysis is None:
        raise LookupError("Este local ainda não tem uma análise real. Rode 'coletar.py diagnostico <local> --analisar'.")
    profile = history.load_profile(analysis)
    if profile is not None:
        result = analyze(profile)
    elif is_current_version(analysis):
        result = analysis["result"]
    else:
        raise LookupError("O bruto da última análise não existe mais e ela é de uma versão anterior do motor. "
                          "Rode de novo com --analisar.")
    itens = []
    for item in result["items"]:
        avaliado = item["status"] in ("good", "fair", "bad")
        titulo, situacao, orientacao, _ = _item_texts(item) if avaliado else (
            texts.TITLES.get(item["id"], item["title"]), "", "", "")
        itens.append({
            "id": item["id"], "titulo": titulo, "status": item["status"], "nota": item["score"],
            "precisaAcao": item["status"] in ("fair", "bad"),
            "situacao": situacao, "orientacao": orientacao, "dados": item["message"].get("vars", {}),
            "comoResolver": COMO_RESOLVER.get(item["id"], "texto"), "campoApi": CAMPO_API.get(item["id"]),
            "cuidado": CUIDADO.get(item["id"]),
        })
    o = result["overall"]
    return {
        "contrato": CONTRATO,
        "local": {"id": location_id, "nome": result["location"]["name"]},
        "analise": {"id": analysis["id"], "data": analysis["analyzed_at"], "nota": o["score"],
                    "bom": o["good"], "razoavel": o["fair"], "fraco": o["bad"], "indisponiveis": o["unavailable"]},
        "perfil": _perfil(profile) if profile is not None else None,
        "itens": itens,
    }
