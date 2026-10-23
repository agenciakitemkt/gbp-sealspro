"""Textos do PDF da Pre Analise para o dono do negocio: situacao atual e orientacao de cada um dos 20 itens.

Mesmas regras de report/texts.py: linguagem clara, sem jargao, so orientacao (sem prazo nem promessa de resultado).
Cada item tem uma funcao que recebe o status ('good', 'fair', 'bad') e as variaveis da analise guardada
(`message.vars`) e devolve (situacao, orientacao). Com status 'good' a orientacao e para MANTER.
"""

from report.texts import STATUS_HELP, STATUS_NAME, _n, _pl, counts_sentence  # noqa: F401 (reexportados para o build)


def _pct(x):
    return _n(round(x)) if float(x).is_integer() else _n(x)


def business_name(s, v):
    if s == "good":
        return (f"O nome do negócio tem {v['current']} caracteres, dentro do limite de {v['recommended']}.",
                "Use sempre o nome real do negócio, como aparece na fachada e nos documentos.")
    return (f"O nome do negócio tem {v['current']} caracteres, acima do limite de {v['recommended']}.",
            "Use o nome real do negócio, sem acrescentar palavras-chave ou slogans, dentro do limite de caracteres.")


def phone(s, v):
    if s == "good":
        return (f"O telefone {v['current']} está cadastrado.",
                "Confira de tempos em tempos se o número continua correto e sendo atendido.")
    return ("O perfil não tem telefone cadastrado.",
            "Cadastre o número principal de atendimento, para o cliente ligar direto pelo Google.")


def website(s, v):
    if s == "good":
        return (f"O perfil aponta para o site {v['current']}.",
                "Verifique de vez em quando se o endereço continua funcionando e leva à página certa.")
    if s == "fair":
        return (f"O link do perfil leva a uma rede social ({v['current']}), e não a um site próprio.",
                "Se tiver um site, mesmo que simples, cadastre-o no lugar da rede social. "
                "As redes sociais podem ser vinculadas ao perfil à parte.")
    return ("O perfil não tem site cadastrado.",
            "Informe o endereço do site, ou de uma página de contato, para o cliente conhecer o negócio "
            "antes de falar com você.")


def hours(s, v):
    if s == "good":
        return ("O horário de funcionamento está informado.",
                "Atualize sempre que o horário mudar, inclusive em feriados.")
    return ("O horário de funcionamento não está informado.",
            "Informe os dias e horários de atendimento. Quem pesquisa quer saber se o negócio está aberto "
            "naquele momento.")


def description(s, v):
    if not v["current"]:
        return ("O perfil não tem descrição.",
                "Escreva um texto que explique o que o negócio faz, para quem, onde atende e o que o diferencia, "
                "usando as palavras que o cliente usaria para procurar o serviço.")
    if s == "good":
        return (f"A descrição tem {v['current']} caracteres e está completa.",
                "Releia a descrição de tempos em tempos e atualize se os serviços ou os diferenciais mudarem.")
    return (f"A descrição tem só {v['current']} caracteres.",
            "Amplie o texto: conte o que o negócio faz, para quem, onde atende e o que o diferencia, "
            "usando as palavras que o cliente usaria para procurar o serviço.")


def logo(s, v):
    if s == "good":
        return ("O logotipo está cadastrado.", "Mantenha a versão atual da marca em todos os canais.")
    return ("O logotipo não está cadastrado.",
            "Envie o logotipo em boa qualidade para que o cliente reconheça a marca na busca e no mapa.")


def verified(s, v):
    if s == "good":
        return ("O perfil é verificado pelo Google.",
                "Mantenha o acesso ao perfil com mais de uma pessoa de confiança da empresa.")
    return ("O perfil não é verificado pelo Google.",
            "Reivindique e verifique o perfil. Só assim o dono controla as informações, responde às avaliações "
            "e publica novidades.")


def social_links(s, v):
    if s == "good":
        return (f"O perfil mostra {_pl(v['current'], 'rede social', 'redes sociais')}: {v['names']}.",
                "Mantenha as redes ativas e com o mesmo nome e a mesma identidade do perfil.")
    return ("Nenhuma rede social aparece vinculada ao perfil.",
            "Vincule ao perfil as redes sociais que o negócio usa, como Instagram e Facebook, para o cliente "
            "encontrar tudo num lugar só.")


def last_post(s, v):
    if v.get("current") is None:
        return ("O perfil ainda não tem postagens.",
                "Comece a publicar novidades, ofertas ou dicas, mesmo que de forma simples.")
    if s == "good":
        return (f"A última postagem foi há {_pl(v['current'], 'dia', 'dias')}.",
                "Mantenha a regularidade com novidades, ofertas e bastidores do negócio.")
    return (f"A última postagem foi há {_pl(v['current'], 'dia', 'dias')}; o ideal é publicar pelo menos a cada "
            f"{v['recommended']} dias.",
            "Publique novidades, ofertas ou dicas com regularidade. Um post curto com uma boa foto já ajuda.")


def last_owner_photo(s, v):
    if v.get("current") is None:
        return ("O dono do perfil ainda não publicou fotos.",
                "Publique fotos do espaço, dos serviços e da equipe. Imagens reais ajudam o cliente a confiar.")
    if s == "good":
        return (f"A última foto publicada pela empresa é de {_pl(v['current'], 'dia', 'dias')} atrás.",
                "Continue renovando as imagens com regularidade.")
    return (f"A última foto publicada pela empresa é de {_pl(v['current'], 'dia', 'dias')} atrás; o ideal é "
            f"publicar fotos novas pelo menos a cada {v['recommended']} dias.",
            "Publique imagens novas do espaço, dos serviços e da equipe. Imagens recentes passam mais confiança.")


def videos(s, v):
    if s == "good":
        return (f"O perfil tem {_pl(v['current'], 'vídeo', 'vídeos')} (recomendado: {v['recommended']}).",
                "Continue renovando os vídeos, mostrando o espaço, a equipe e o atendimento.")
    return (f"O perfil tem {v['current']} de {v['recommended']} vídeos recomendados.",
            "Publique vídeos curtos: um passeio pelo espaço, a equipe em ação ou um serviço sendo realizado.")


def photos_360(s, v):
    if s == "good":
        return (f"O perfil tem {v['current']} imagens em 360°.",
                "Atualize as imagens em 360° quando o espaço mudar.")
    return ("O perfil tem menos de duas imagens em 360°.",
            "Publique fotos em 360° do interior e da fachada, para o cliente conhecer o espaço antes de ir.")


def reviews_count(s, v):
    if s == "good":
        return (f"O perfil tem {_pl(v['current'], 'avaliação', 'avaliações')} "
                f"(mínimo recomendado: {v['recommended']}).",
                "Continue pedindo a avaliação a cada cliente atendido.")
    return (f"O perfil tem só {_pl(v['current'], 'avaliação', 'avaliações')}; o mínimo recomendado é "
            f"{v['recommended']}.",
            "Peça a avaliação a clientes satisfeitos logo após o atendimento, enviando o link direto para avaliar. "
            "Não ofereça brindes ou descontos em troca, pois o Google não permite.")


def reviews_average(s, v):
    if "current" not in v:
        return ("O perfil ainda não tem avaliações para calcular a nota média.",
                "Peça as primeiras avaliações a clientes satisfeitos, enviando o link direto para avaliar.")
    if s == "good":
        return (f"A nota média das avaliações é {_n(v['current'])} estrelas.",
                "Mantenha a qualidade do atendimento e responda a todas as avaliações.")
    return (f"A nota média das avaliações é {_n(v['current'])} estrelas; o ideal é a partir de "
            f"{_n(v['recommended'])}.",
            "Entenda o que motiva as notas baixas, responda com educação e corrija os problemas apontados. "
            "Atender bem quem reclamou também melhora a imagem do negócio.")


def last_review(s, v):
    if v.get("current") is None:
        return ("O perfil ainda não tem avaliações.",
                "Peça as primeiras avaliações a clientes satisfeitos, enviando o link direto para avaliar.")
    if s == "good":
        return (f"A avaliação mais recente chegou há {_pl(v['current'], 'dia', 'dias')}.",
                "Continue pedindo a avaliação a cada cliente atendido.")
    return (f"A avaliação mais recente chegou há {_pl(v['current'], 'dia', 'dias')}; o ideal é receber ao menos "
            f"uma a cada {v['recommended']} dias.",
            "Torne o pedido de avaliação parte do atendimento, enviando o link direto para avaliar "
            "a cada cliente satisfeito.")


def reviews_trend(s, v):
    recent, average = _n(v["recent"]), _n(v["average"])
    if s == "good":
        verb = "está acima da" if v["recent"] > v["average"] else "acompanha a"
        return (f"A média das avaliações mais recentes ({recent}) {verb} média das avaliações analisadas "
                f"({average}).",
                "Mantenha o padrão de atendimento.")
    return (f"A média das avaliações mais recentes ({recent}) está abaixo da média das avaliações analisadas "
            f"({average}).",
            "Veja o que mudou no atendimento, leia as avaliações recentes e converse com a equipe sobre os "
            "pontos citados.")


def reviews_unanswered(s, v):
    share = f"{v['current']} de {v['size']} avaliações analisadas ({_pct(v['percent'])}%)"
    if s == "good":
        if not v["current"]:
            return (f"Todas as {v['size']} avaliações analisadas foram respondidas.",
                    "Continue respondendo às novas avaliações assim que chegarem.")
        return (f"Só {share} estão sem resposta.",
                "Continue respondendo às novas avaliações assim que chegarem.")
    return (f"{share} estão sem resposta.",
            "Responda a cada avaliação, agradecendo os elogios e, nas críticas, com educação e uma solução. "
            "Isso mostra que o negócio se importa com o cliente.")


def reviews_with_text(s, v):
    share = f"{v['current']} de {v['size']} avaliações analisadas ({_pct(v['percent'])}%)"
    if s == "good":
        return (f"{share} trazem comentário.",
                "Continue convidando os clientes a contar como foi a experiência.")
    return (f"Só {share} trazem comentário; o restante tem apenas as estrelas.",
            "Ao pedir a avaliação, convide o cliente a escrever uma ou duas frases sobre o atendimento. "
            "Comentários ajudam novos clientes a decidir.")


def top10_reviews(s, v):
    if s == "good":
        return (f"Com {_pl(v['current'], 'avaliação', 'avaliações')}, o negócio está entre os 10 mais avaliados "
                f"dos {v['competitors']} concorrentes do segmento encontrados na região.",
                "Continue pedindo avaliações para manter a posição.")
    return (f"Com {_pl(v['current'], 'avaliação', 'avaliações')}, o negócio não está entre os 10 mais avaliados "
            f"dos {v['competitors']} concorrentes do segmento encontrados na região.",
            "Peça a avaliação a cada cliente satisfeito. A quantidade de avaliações é um dos pontos que o cliente "
            "compara entre os negócios.")


def above_segment_average(s, v):
    avg = _n(round(v["average"]))
    if s == "good":
        return (f"O negócio tem {_pl(v['current'], 'avaliação', 'avaliações')}, acima da média de {avg} dos "
                "concorrentes do segmento na região.",
                "Continue pedindo avaliações para manter a vantagem.")
    return (f"O negócio tem {_pl(v['current'], 'avaliação', 'avaliações')}, abaixo da média de {avg} dos "
            "concorrentes do segmento na região.",
            "Peça a avaliação a cada cliente satisfeito, enviando o link direto para avaliar.")


TITLES = {
    "business_name": "Nome do negócio", "phone": "Telefone", "website": "Site",
    "hours": "Horário de funcionamento", "description": "Descrição do negócio", "logo": "Logotipo",
    "verified": "Perfil verificado", "social_links": "Redes sociais no perfil", "last_post": "Última postagem",
    "last_owner_photo": "Última foto publicada pela empresa", "videos": "Vídeos", "photos_360": "Imagens em 360°",
    "reviews_count": "Quantidade de avaliações", "reviews_average": "Nota média das avaliações",
    "last_review": "Avaliação mais recente", "reviews_trend": "Tendência das avaliações",
    "reviews_unanswered": "Avaliações sem resposta", "reviews_with_text": "Avaliações com comentário",
    "top10_reviews": "Entre os 10 mais avaliados da região", "above_segment_average": "Avaliações frente aos concorrentes",
}
TEXTS = {k: globals()[k] for k in TITLES}

UNAVAILABLE = "Não foi possível coletar este dado."


def describe(item_id, status, variables):
    """(titulo, situacao, orientacao, tipo) de um item avaliado. tipo = 'manter' (bom) ou 'fazer' (abaixo do ideal)."""
    situation, advice = TEXTS[item_id](status, variables)
    return TITLES[item_id], situation, advice, "manter" if status == "good" else "fazer"


def overall_sentences(status, counts):
    """Duas frases sobre o que a nota significa (o perfil ainda nao e cliente: tom de diagnostico)."""
    first = {"good": "O perfil está em ótimo estado: restam poucos pontos a ajustar.",
             "fair": "O perfil está em um nível razoável: há oportunidades claras de melhoria.",
             "bad": "O perfil precisa de atenção: há pontos importantes a corrigir."}[status]
    return first, counts_sentence(counts)
