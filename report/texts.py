"""Textos do relatorio para o cliente final: situacao atual e orientacao de cada um dos 21 itens.

Linguagem clara, sem jargao tecnico, tom profissional. So orientacao: sem prazo e sem promessa de resultado.
Cada item tem uma funcao `good` (item em bom estado) e uma `low` (abaixo do ideal), que recebem as variaveis
da analise guardada (`message.vars`) e devolvem (situacao, orientacao). Em `good` a orientacao e para MANTER.
"""

from datetime import datetime


def _pl(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _n(x):
    """Decimal com virgula."""
    return str(x).replace(".", ",")


def _date(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y")


# ---- um bloco por item: (titulo para o cliente, good(v), low(v)) --------------------------------------------

def phone_good(v):
    return (f"O telefone {v['current']} está cadastrado.",
            "Confira de tempos em tempos se o número continua correto e sendo atendido.")


def phone_low(v):
    return ("Seu perfil não tem telefone cadastrado.",
            "Cadastre o número principal de atendimento, o mesmo usado no site e nas redes sociais, "
            "para o cliente ligar direto pelo Google.")


def website_good(v):
    return (f"Seu perfil aponta para o site {v['current']}.",
            "Verifique de vez em quando se o endereço continua funcionando e leva à página certa.")


def website_low(v):
    return ("Seu perfil não tem site cadastrado.",
            "Informe o endereço do site, ou de uma página de contato, para o cliente conhecer a empresa "
            "antes de falar com você.")


def hours_good(v):
    return (f"O horário de funcionamento está informado para {_pl(v['current'], 'dia', 'dias')} da semana.",
            "Atualize sempre que o horário mudar, inclusive em feriados prolongados.")


def hours_low(v):
    return ("O horário de funcionamento não está informado.",
            "Informe os dias e horários de atendimento. Quem pesquisa quer saber se a empresa está aberta "
            "naquele momento.")


def special_hours_good(v):
    return (f"Há {_pl(v['current'], 'data especial cadastrada', 'datas especiais cadastradas')} para {v['year']}.",
            "Acrescente novas datas, como feriados e recessos, conforme o ano avança.")


def special_hours_low(v):
    return (f"Nenhuma data especial está cadastrada para {v['year']}.",
            "Cadastre os feriados e os dias em que a empresa fecha ou abre em horário diferente, "
            "para o cliente não chegar e encontrar a porta fechada.")


def description_good(v):
    return (f"A descrição tem {v['current']} caracteres, acima do mínimo recomendado de {v['recommended']}.",
            "Releia a descrição de tempos em tempos e atualize se os serviços ou os diferenciais mudarem.")


def description_low(v):
    return (f"A descrição tem só {v['current']} caracteres; o mínimo recomendado é {v['recommended']}.",
            "Escreva um texto que explique o que a empresa faz, para quem, onde atende e o que a diferencia, "
            "usando as palavras que o cliente usaria para procurar o serviço.")


def videos_good(v):
    return (f"Seu perfil tem {_pl(v['current'], 'vídeo publicado', 'vídeos publicados')} "
            f"(recomendado: {v['recommended']}).",
            "Continue renovando os vídeos, mostrando o espaço, a equipe e o atendimento.")


def videos_low(v):
    return (f"Seu perfil tem {v['current']} de {v['recommended']} vídeos recomendados.",
            "Publique vídeos curtos: um passeio pelo espaço, a equipe em ação ou um serviço sendo realizado.")


def logo_good(v):
    return ("O logotipo está cadastrado.", "Mantenha a versão atual da marca em todos os canais.")


def logo_low(v):
    return ("O logotipo não está cadastrado.",
            "Envie o logotipo em boa qualidade para que o cliente reconheça a marca na busca e no mapa.")


def cover_good(v):
    return ("A foto de capa está definida.",
            "Troque a capa quando tiver uma foto melhor ou uma campanha para destacar.")


def cover_low(v):
    return ("Seu perfil não tem foto de capa.",
            "Escolha uma foto que represente bem a empresa, como a fachada, o ambiente ou a equipe, "
            "para ser a primeira imagem que o cliente vê.")


def owner_media_good(v):
    return (f"A empresa publicou {_pl(v['current'], 'foto ou vídeo', 'fotos e vídeos')} "
            f"(recomendado: {v['recommended']}).",
            "Continue adicionando imagens novas do espaço, dos serviços e da equipe.")


def owner_media_low(v):
    return (f"A empresa publicou {v['current']} de {v['recommended']} fotos e vídeos recomendados.",
            "Adicione fotos do exterior, do interior, da equipe e dos serviços. Imagens reais ajudam o cliente "
            "a confiar antes de visitar.")


def total_media_good(v):
    return (f"O perfil reúne {_pl(v['current'], 'foto ou vídeo', 'fotos e vídeos')} no total, somando os da empresa "
            f"e os enviados por clientes (recomendado: {v['recommended']}).",
            "Continue alimentando o perfil com imagens novas.")


def total_media_low(v):
    return (f"O perfil reúne {v['current']} de {v['recommended']} fotos e vídeos recomendados no total, somando os da "
            "empresa e os enviados por clientes.",
            "Aumente a quantidade de imagens publicando fotos novas e estimulando os clientes a compartilhar as deles.")


def customer_media_good(v):
    return (f"Clientes enviaram {_pl(v['current'], 'foto ou vídeo', 'fotos e vídeos')} "
            f"(recomendado: {v['recommended']}).",
            "Agradeça quando um cliente compartilhar uma imagem e continue incentivando.")


def customer_media_low(v):
    return (f"Clientes enviaram {v['current']} de {v['recommended']} fotos e vídeos recomendados.",
            "Convide clientes satisfeitos a compartilhar uma foto do ambiente ou do atendimento, "
            "junto com a avaliação.")


def reviews_count_good(v):
    return (f"Seu perfil tem {_pl(v['current'], 'avaliação', 'avaliações')} (mínimo recomendado: {v['recommended']}).",
            "Continue pedindo a avaliação a cada cliente atendido.")


def reviews_count_low(v):
    return (f"Seu perfil tem só {_pl(v['current'], 'avaliação', 'avaliações')}; o mínimo recomendado é "
            f"{v['recommended']}.",
            "Peça a avaliação a clientes satisfeitos logo após o atendimento, enviando o link direto para avaliar. "
            "Não ofereça brindes ou descontos em troca, pois o Google não permite.")


def reviews_average_good(v):
    return (f"A nota média das avaliações é {_n(v['current'])} estrelas.",
            "Mantenha a qualidade do atendimento e responda a todas as avaliações.")


def reviews_average_low(v):
    if "recommended" not in v:  # ainda sem avaliacoes
        return ("Seu perfil ainda não tem avaliações para calcular a nota média.",
                "Peça as primeiras avaliações a clientes satisfeitos, enviando o link direto para avaliar.")
    return (f"A nota média das avaliações é {_n(v['current'])} estrelas, abaixo do nível desejado.",
            "Entenda o que motiva as notas baixas, responda com educação e corrija os problemas apontados. "
            "Atender bem quem reclamou também melhora a imagem da empresa.")


def reviews_unanswered_good(v):
    if v["total"] == 0:
        return ("Seu perfil ainda não tem avaliações para responder.",
                "Quando chegarem as primeiras avaliações, responda a todas.")
    todas = "A única avaliação foi respondida." if v["total"] == 1 else f"Todas as {v['total']} avaliações foram respondidas."
    return (todas, "Continue respondendo às novas avaliações assim que chegarem.")


def reviews_unanswered_low(v):
    return (f"{_pl(v['current'], 'avaliação ainda está', 'avaliações ainda estão')} sem resposta "
            f"(de {v['total']} no total).",
            "Responda a cada avaliação, agradecendo os elogios e, nas críticas, com educação e uma solução. "
            "Isso mostra que a empresa se importa com o cliente.")


def reviews_no_comment_good(v):
    return (f"{v['percent']}% das avaliações vêm sem comentário, dentro do esperado.",
            "Continue convidando os clientes a contar como foi a experiência.")


def reviews_no_comment_low(v):
    if v["total"] == 0:
        return ("Ainda não há avaliações para medir os comentários.",
                "Quando chegarem as primeiras avaliações, convide o cliente a escrever como foi o atendimento.")
    return (f"{v['percent']}% das avaliações ({v['current']} de {v['total']}) trazem só as estrelas, sem comentário.",
            "Ao pedir a avaliação, convide o cliente a escrever uma ou duas frases sobre o atendimento. "
            "Comentários ajudam novos clientes a decidir.")


def services_good(v):
    return (f"Seu perfil lista {_pl(v['current'], 'serviço', 'serviços')}.",
            "Atualize a lista quando incluir ou retirar serviços.")


def services_low(v):
    return ("Seu perfil não tem serviços cadastrados.",
            "Liste os serviços oferecidos, com nomes claros e, se possível, uma frase explicando cada um.")


def founding_date_good(v):
    return (f"A data de abertura da empresa está informada ({_date(v['current'])}).",
            "Mantenha a informação correta.")


def founding_date_low(v):
    return ("A data de abertura da empresa não está informada.",
            "Informe a data de abertura. Ela mostra há quanto tempo a empresa atua.")


def business_name_good(v):
    return (f"O nome da empresa tem {v['current']} caracteres, dentro do limite de {v['recommended']}.",
            "Use sempre o nome real da empresa, como aparece na fachada e nos documentos.")


def business_name_low(v):
    return (f"O nome da empresa tem {v['current']} caracteres, acima do limite de {v['recommended']}.",
            "Use o nome real da empresa, sem acrescentar palavras-chave ou slogans, dentro do limite de caracteres.")


def reviews_trend_good(v):
    if "recent" not in v:  # sem avaliacoes recentes e antigas para comparar
        return ("Ainda não há avaliações recentes e antigas suficientes para comparar a evolução.",
                "Continue recebendo avaliações para acompanhar a evolução ao longo do tempo.")
    if v["trend"] == "up":
        return (f"A média das avaliações dos últimos {v['days']} dias ({_n(v['recent'])}) está acima da média anterior "
                f"({_n(v['historical'])}).",
                "Continue com o que está funcionando no atendimento.")
    return (f"A média das avaliações dos últimos {v['days']} dias ({_n(v['recent'])}) acompanha a média anterior "
            f"({_n(v['historical'])}).",
            "Mantenha o padrão de atendimento.")


def reviews_trend_low(v):
    return (f"A média das avaliações dos últimos {v['days']} dias ({_n(v['recent'])}) está abaixo da média anterior "
            f"({_n(v['historical'])}).",
            "Veja o que mudou no atendimento desde então, leia as avaliações recentes e converse com a equipe "
            "sobre os pontos citados.")


def last_post_good(v):
    return (f"A última postagem foi há {_pl(v['current'], 'dia', 'dias')}.",
            "Mantenha a regularidade com novidades, ofertas e bastidores da empresa.")


def last_post_low(v):
    if v["current"] is None:
        return ("Seu perfil ainda não tem postagens.",
                "Comece a publicar novidades, ofertas ou dicas, mesmo que de forma simples.")
    return (f"A última postagem foi há {_pl(v['current'], 'dia', 'dias')}; o ideal é publicar pelo menos a cada "
            f"{v['recommended']} dias.",
            "Publique novidades, ofertas ou dicas com regularidade. Um post curto com uma boa foto já ajuda.")


def last_owner_media_good(v):
    return (f"A última foto ou vídeo da empresa foi publicado há {_pl(v['current'], 'dia', 'dias')}.",
            "Continue renovando as imagens com regularidade.")


def last_owner_media_low(v):
    if v["current"] is None:
        return ("Seu perfil não tem fotos ou vídeos da empresa com data conhecida.",
                "Publique imagens do espaço, dos serviços e da equipe.")
    return (f"A última foto ou vídeo da empresa foi publicado há {_pl(v['current'], 'dia', 'dias')}; o ideal é "
            "renovar a cada cerca de dois meses.",
            "Publique imagens novas do espaço, dos serviços e da equipe. Imagens recentes passam mais confiança.")


TITLES = {
    "phone": "Telefone", "website": "Site", "hours": "Horário de funcionamento",
    "special_hours": "Feriados e datas especiais", "description": "Descrição da empresa", "videos": "Vídeos",
    "logo": "Logotipo", "cover": "Foto de capa", "owner_media": "Fotos e vídeos da empresa",
    "total_media": "Total de fotos e vídeos no perfil", "customer_media": "Fotos e vídeos de clientes",
    "reviews_count": "Quantidade de avaliações", "reviews_average": "Nota média das avaliações",
    "reviews_unanswered": "Avaliações sem resposta", "reviews_no_comment": "Avaliações sem comentário",
    "services": "Serviços cadastrados", "founding_date": "Data de abertura", "business_name": "Nome da empresa",
    "reviews_trend": "Tendência das avaliações", "last_post": "Última postagem",
    "last_owner_media": "Última foto ou vídeo publicado",
}
GOOD = {k: globals()[f"{k}_good"] for k in TITLES}
LOW = {k: globals()[f"{k}_low"] for k in TITLES}

UNAVAILABLE = "Não foi possível coletar este dado."
NOT_APPLICABLE = "Não se aplica ao tipo de negócio deste perfil."

STATUS_NAME = {"bad": "Fraco", "fair": "Razoável", "good": "Bom"}
STATUS_HELP = {"bad": "precisam de atenção", "fair": "podem melhorar", "good": "em ótimo estado"}


def describe(item_id, status, variables):
    """(titulo, situacao, orientacao, tipo) de um item avaliado. tipo = 'manter' (bom) ou 'fazer' (abaixo do ideal)."""
    if status == "good":
        situation, advice = GOOD[item_id](variables)
        return TITLES[item_id], situation, advice, "manter"
    situation, advice = LOW[item_id](variables)
    return TITLES[item_id], situation, advice, "fazer"


def overall_sentences(status, counts):
    """Duas frases sobre o que a nota significa."""
    first = {"good": "Seu perfil está em ótimo estado: restam poucos pontos a ajustar.",
             "fair": "Seu perfil está em um nível razoável: há oportunidades claras de melhoria.",
             "bad": "Seu perfil precisa de atenção: há pontos importantes a corrigir."}[status]
    return first, counts_sentence(counts)


def counts_sentence(counts):
    """'Dos 20 itens avaliados, 14 estão em bom estado, 1 pode melhorar e 5 precisam de atenção.'"""
    g, f, b = counts["good"], counts["fair"], counts["bad"]
    return (f"Dos {g + f + b} itens avaliados, {g} {'está' if g == 1 else 'estão'} em bom estado, "
            f"{f} {'pode' if f == 1 else 'podem'} melhorar e {b} {'precisa' if b == 1 else 'precisam'} de atenção.")
