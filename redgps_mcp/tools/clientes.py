# =============================================================================
# tools/clientes.py
# =============================================================================
#
# OBJETIVO:
#   Este arquivo registra todas as "tools" (ferramentas) do MCP Server
#   relacionadas a CLIENTES, USUÁRIOS, CONDUTORES, TICKETS e MÓDULOS.
#
# COMO FUNCIONA:
#   - Cada função decorada com @mcp.tool() vira uma ferramenta que o Claude
#     pode chamar automaticamente quando o usuário digita algo em linguagem
#     natural no chat.
#   - A docstring de cada tool é o "prompt" que o Claude lê para decidir
#     QUANDO e COMO usar a ferramenta. Por isso ela deve ser clara e completa.
#   - A API do RedGPS usa form-data (não JSON) e mistura campos em
#     espanhol e inglês — por isso usamos helpers flexíveis.
#
# ESTRUTURA DO ARQUIVO:
#   1. Imports e configurações
#   2. Helpers reutilizáveis (executar_post, get_campo, formatar_ativo)
#   3. Registro das tools via registrar_tools_clientes(mcp)
#
# =============================================================================

import asyncio
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional
from utils.api_client import post, tratar_erro

# Tempo máximo (em segundos) que esperamos uma resposta da API RedGPS.
# Se demorar mais, lançamos TimeoutError (tratado em tratar_erro).
TIMEOUT_API = 15


# =============================================================================
# HELPERS REUTILIZÁVEIS
# =============================================================================

async def executar_post(endpoint: str, payload: dict | None = None) -> list | dict:
    """
    Centraliza a lógica de chamada à API RedGPS com timeout e validação.

    POR QUE USAR ISSO?
      - Evita repetir o mesmo bloco try/await/timeout em cada tool.
      - Garante que sempre verificamos o campo "status" da resposta.
      - Lança Exception com mensagem clara se a API retornar erro.

    PARÂMETROS:
      endpoint : nome do endpoint sem a URL base (ex: "getMyUser")
      payload  : dicionário com parâmetros extras além de apikey/token
                 (apikey e token são injetados automaticamente em api_client.py)

    RETORNA:
      O valor de resultado["data"], que pode ser dict ou list dependendo
      do endpoint chamado.
    """
    resultado = await asyncio.wait_for(
        post(endpoint, payload),   # post() está em utils/api_client.py
        timeout=TIMEOUT_API
    )

    if resultado.get("status") != 200:
        raise Exception(
            f"API retornou status {resultado.get('status')}: {resultado}"
        )

    return resultado.get("data", {})


def get_campo(*chaves: str, dados: dict, fallback: str = "N/A") -> str:
    """
    Tenta múltiplas chaves em um dicionário e retorna o primeiro valor válido.

    POR QUE PRECISAMOS DISSO?
      A API do RedGPS mistura nomes de campos em espanhol (nombre, telefono,
      activo) e em inglês (name, phone, active). Para não perder dados,
      tentamos todas as variações possíveis antes de retornar "N/A".

    EXEMPLO:
      get_campo("name", "nombre", dados=condutor_dict)
      → Tenta "name" primeiro, depois "nombre", retorna o primeiro não vazio.

    PARÂMETROS:
      *chaves  : lista variável de chaves para tentar (ordem importa)
      dados    : o dicionário onde buscar
      fallback : valor padrão se nenhuma chave retornar algo útil
    """
    for chave in chaves:
        valor = dados.get(chave)
        # Ignora None, string vazia, zero e "0" — todos considerados "sem dado"
        if valor not in [None, "", 0, "0"]:
            return str(valor)
    return fallback


def formatar_ativo(dados: dict) -> str:
    """
    Lê o campo de status ativo/inativo de um objeto e retorna emoji + texto.

    A API RedGPS usa nomes diferentes dependendo do endpoint:
      - "active"  (inglês, valor True/False ou 1/0)
      - "activo"  (espanhol, valor True/False ou 1/0)
      - "status"  (inteiro: 1 = ativo, 0 = inativo)
    """
    ativo = dados.get("active") or dados.get("activo") or dados.get("status")
    if ativo in [True, 1, "1", "true", "True"]:
        return "✅ Ativo"
    return "⛔ Inativo"


# =============================================================================
# REGISTRO DAS TOOLS MCP
# =============================================================================
#
# ENGENHARIA DE PROMPTS — PRINCÍPIOS USADOS AQUI:
#
# 1. DOCSTRING DESCRITIVA:
#    A docstring é o que o Claude lê para decidir quando chamar a tool.
#    Deve responder: "O que faz?", "Quando usar?" e "Exemplos de perguntas".
#
# 2. PARÂMETROS COM FIELD():
#    Field(description=...) serve como instrução ao Claude sobre o que
#    colocar em cada parâmetro. Quanto mais específico, melhor.
#
# 3. RESPOSTAS FORMATADAS:
#    O Claude apresenta o retorno da tool diretamente ao usuário.
#    Por isso usamos Markdown (tabelas, negrito, emojis) para deixar
#    a resposta visualmente organizada no chat.
#
# =============================================================================

def registrar_tools_clientes(mcp: FastMCP):
    """
    Registra todas as tools de clientes no servidor MCP.

    Esta função é chamada uma vez em server.py durante a inicialização.
    Cada @mcp.tool() dentro dela adiciona uma ferramenta ao servidor.
    """

    # =========================================================================
    # TOOL: dados_cliente
    # ENDPOINT: POST /getClientData (fallback: /getMyUser)
    # =========================================================================
    @mcp.tool(name="dados_cliente")
    async def dados_cliente() -> str:
        """
        Retorna os dados completos do cliente/empresa associado à conta atual.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Dados da empresa ou conta (nome, e-mail, telefone, cidade)
        - Quantos ativos/veículos a conta suporta (max_assets)
        - Quantos ativos estão cadastrados (assets_count)
        - Informações do perfil da empresa no RedGPS

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Quais são os dados da minha conta?"
        - "Qual o nome da empresa cadastrada?"
        - "Quantos veículos minha conta suporta?"
        - "Me mostra o perfil da empresa"

        NÃO USE para perguntas sobre o usuário individual — use meu_usuario.
        """
        try:
            dados = {}

            # Tentativa 1: endpoint dedicado para dados do cliente
            # Documentação: POST /getClientData → retorna dict ou list com info da empresa
            try:
                dados = await executar_post("getClientData")
                # Alguns perfis retornam lista com um único item — normalizamos para dict
                if isinstance(dados, list):
                    dados = dados[0] if dados else {}
            except Exception:
                # Se getClientData falhar (permissão ou indisponível), usamos fallback
                pass

            # Tentativa 2 (fallback): getMyUser também embute dados do cliente
            # A API retorna dados do usuário + empresa no mesmo objeto
            if not dados:
                resultado_user = await asyncio.wait_for(
                    post("getMyUser"), timeout=TIMEOUT_API
                )
                user_data = resultado_user.get("data", {})
                # getMyUser pode ter os dados do cliente em subcampo "client"
                dados = user_data.get("client") or user_data

            if not dados:
                return "Nenhum dado encontrado para este cliente."

            # Monta a resposta usando Markdown para exibição no chat
            linhas = ["📄 **Dados do Cliente:**\n"]

            # Lista de campos que queremos exibir
            # Formato: (["chave_ingles", "chave_espanhol"], "Rótulo exibido")
            mapeamento = [
                (["name", "nombre", "razonsocial"],       "Nome / Razão Social"),
                (["email", "correo"],                      "E-mail"),
                (["phone", "telefono", "telefone"],        "Telefone"),
                (["country", "pais"],                      "País"),
                (["state", "estado", "provincia"],         "Estado / Província"),
                (["city", "ciudad", "cidade"],             "Cidade"),
                (["address", "direccion", "endereco"],     "Endereço"),
                (["id", "idclient", "id_client"],          "ID do Cliente"),
                (["max_assets", "max_activos"],            "Máx. Ativos/Veículos"),
                (["assets_count", "total_activos"],        "Ativos Cadastrados"),
                (["timezone", "zona_horaria"],             "Fuso Horário"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Status:** {formatar_ativo(dados)}")
            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: meu_usuario
    # ENDPOINT: POST /getMyUser
    # =========================================================================
    @mcp.tool(name="meu_usuario")
    async def meu_usuario() -> str:
        """
        Retorna as informações do usuário autenticado com o token atual.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Seu próprio login, nome de usuário ou perfil de acesso
        - Qual seu nível de permissão ou papel (role/perfil)
        - Seus dados pessoais de cadastro no RedGPS

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Quais são meus dados de usuário?"
        - "Qual meu login no sistema?"
        - "Qual meu perfil de acesso?"
        - "Me mostra meu cadastro"

        DIFERENÇA para dados_cliente:
        - meu_usuario → dados do LOGIN (pessoa física, acesso)
        - dados_cliente → dados da EMPRESA/CONTA (pessoa jurídica, contrato)
        """
        try:
            # Documentação: POST /getMyUser
            # Retorna dados do usuário logado: username, name, email, role, etc.
            dados = await executar_post("getMyUser")

            # Normaliza: alguns planos retornam lista, outros dict
            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            if not dados:
                return "Nenhuma informação de usuário encontrada."

            linhas = ["👤 **Meu Usuário:**\n"]

            mapeamento = [
                (["username", "usuario", "login"],        "Usuário / Login"),
                (["name", "nombre", "nome"],              "Nome Completo"),
                (["email", "correo"],                     "E-mail"),
                (["phone", "telefono", "telefone"],       "Telefone"),
                # "role" define o nível de acesso: admin, operador, visualizador, etc.
                (["role", "perfil", "rol", "nivel"],      "Perfil de Acesso"),
                (["idclient", "id_client", "idcliente"],  "ID do Cliente Vinculado"),
                (["language", "idioma", "lang"],          "Idioma"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Status:** {formatar_ativo(dados)}")
            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_clientes
    # ENDPOINT: POST /getClients
    # REQUER: acesso nível DISTRIBUIDOR
    # =========================================================================
    @mcp.tool(name="listar_clientes")
    async def listar_clientes() -> str:
        """
        Lista todos os clientes/empresas cadastrados na plataforma.

        IMPORTANTE: Esta tool requer acesso de nível distribuidor.
        Se o usuário tiver apenas acesso de cliente final, retornará erro de permissão.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quantos clientes existem na plataforma
        - Lista de empresas/contas cadastradas
        - Status (ativo/inativo) de cada cliente

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Liste todos os clientes"
        - "Quantas empresas estão cadastradas?"
        - "Quais clientes estão ativos?"
        - "Me dá a lista de contas"
        """
        try:
            # Documentação: POST /getClients
            # Sem parâmetros extras além de apikey/token
            # Retorna lista de objetos com dados de cada cliente
            clientes = await executar_post("getClients")

            # Normaliza caso retorne dict único em vez de lista
            if isinstance(clientes, dict):
                clientes = [clientes]

            if not clientes:
                return "Nenhum cliente encontrado."

            linhas = [
                f"📋 **Total de clientes: {len(clientes)}**\n",
                "| # | Nome / Razão Social | ID | Status |",
                "|---|---------------------|----|--------|"
            ]

            for i, c in enumerate(clientes, 1):
                nome   = get_campo("name", "nombre", "razonsocial", dados=c)
                id_c   = get_campo("id", "idclient", "id_client",   dados=c)
                status = formatar_ativo(c)
                linhas.append(f"| {i} | {nome} | {id_c} | {status} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_usuarios
    # ENDPOINT: POST /getUsers
    # PARÂMETRO OPCIONAL: idclient (filtra por cliente específico)
    # =========================================================================

    # PYDANTIC MODEL — Define os parâmetros que o Claude pode passar para a tool.
    # Field(description=...) serve como instrução ao Claude sobre o que colocar.
    class ListarUsuariosInput(BaseModel):
        id_cliente: Optional[str] = Field(
            None,
            description=(
                "ID numérico do cliente para filtrar os usuários. "
                "Use None ou deixe em branco para listar todos os usuários de todos os clientes. "
                "Obtenha o ID via listar_clientes se necessário."
            )
        )

    @mcp.tool(name="listar_usuarios")
    async def listar_usuarios(params: ListarUsuariosInput) -> str:
        """
        Lista os usuários cadastrados, com opção de filtrar por cliente específico.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quais usuários têm acesso ao sistema
        - Logins cadastrados para um cliente
        - Quem pode acessar a plataforma

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Liste os usuários cadastrados"
        - "Quais logins existem para o cliente 42?"
        - "Quem tem acesso ao sistema?"
        - "Me dá a lista de usuários do cliente ID 10"

        FLUXO RECOMENDADO:
        Se o usuário mencionar o nome de um cliente (não o ID),
        chame listar_clientes primeiro para descobrir o ID,
        depois chame listar_usuarios com o ID correto.
        """
        try:
            # Documentação: POST /getUsers
            # Parâmetro opcional: idclient → filtra pelo ID do cliente
            payload = {"idclient": params.id_cliente} if params.id_cliente else {}
            usuarios = await executar_post("getUsers", payload)

            if isinstance(usuarios, dict):
                usuarios = [usuarios]

            if not usuarios:
                return "Nenhum usuário encontrado."

            linhas = [
                f"👥 **Total de usuários: {len(usuarios)}**\n",
                "| # | Nome | Usuário | E-mail | Perfil | Ativo |",
                "|---|------|---------|--------|--------|-------|"
            ]

            for i, u in enumerate(usuarios, 1):
                nome     = get_campo("name", "nombre",              dados=u)
                username = get_campo("username", "usuario", "login", dados=u)
                email    = get_campo("email", "correo",             dados=u)
                perfil   = get_campo("role", "perfil", "rol",       dados=u)
                ativo    = "✅" if u.get("active") or u.get("activo") else "⛔"
                linhas.append(f"| {i} | {nome} | {username} | {email} | {perfil} | {ativo} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_condutores
    # ENDPOINT: POST /driverGetAll
    # =========================================================================
    @mcp.tool(name="listar_condutores")
    async def listar_condutores() -> str:
        """
        Lista todos os condutores/motoristas cadastrados na plataforma.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Condutores ou motoristas cadastrados
        - Quem são os drivers da frota
        - Lista de habilitações ou documentos de condutores

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Liste os condutores"
        - "Quais motoristas estão cadastrados?"
        - "Me mostra os drivers da frota"
        - "Quantos condutores temos?"

        NOTA: Para buscar um condutor específico pelo documento,
        use a tool buscar_condutor.
        """
        try:
            # Documentação: POST /driverGetAll
            # Sem parâmetros extras além de apikey/token
            # Retorna lista com nome, documento, telefone, status de cada condutor
            condutores = await executar_post("driverGetAll")

            if isinstance(condutores, dict):
                condutores = [condutores]

            if not condutores:
                return "Nenhum condutor encontrado."

            linhas = [
                f"🧑‍✈️ **Total de condutores: {len(condutores)}**\n",
                "| # | Nome | Documento | Telefone | Grupo | Ativo |",
                "|---|------|-----------|----------|-------|-------|"
            ]

            for i, c in enumerate(condutores, 1):
                nome  = get_campo("name", "nombre",                              dados=c)
                # A API usa "documento", "idcard" ou "cedula" dependendo da versão
                doc   = get_campo("documento", "idcard", "cedula",
                                  "numero_documento",                             dados=c)
                tel   = get_campo("phone", "telefono", "telefone",               dados=c)
                grupo = get_campo("grupo", "group", "grupo_conductor",           dados=c)
                ativo = "✅" if c.get("active") or c.get("activo") else "⛔"
                linhas.append(f"| {i} | {nome} | {doc} | {tel} | {grupo} | {ativo} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: buscar_condutor
    # ENDPOINT: POST /getDriverByIdCard
    # PARÂMETRO OBRIGATÓRIO: idcard (número do documento)
    # =========================================================================
    class BuscarCondutorInput(BaseModel):
        documento: str = Field(
            ...,   # ... significa obrigatório no Pydantic
            description=(
                "Número do documento do condutor: CPF, CNH, RG ou qualquer "
                "identificador numérico cadastrado. "
                "Exemplo: '12345678900' ou '98765432'"
            )
        )

    @mcp.tool(name="buscar_condutor")
    async def buscar_condutor(params: BuscarCondutorInput) -> str:
        """
        Busca e retorna os dados completos de um condutor pelo número do documento.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Um motorista específico identificado por CPF, CNH ou RG
        - Dados de um condutor que quer verificar pelo documento

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Busca o condutor com documento 12345678900"
        - "Quem é o motorista com CPF 987.654.321-00?"
        - "Me dá os dados do driver com carteira 123456"

        FLUXO:
        Se o usuário mencionar o nome (não o documento), use listar_condutores
        primeiro para encontrar o documento, depois chame esta tool.
        """
        try:
            # Documentação: POST /getDriverByIdCard
            # Parâmetro: idcard → número do documento do condutor
            dados = await executar_post(
                "getDriverByIdCard",
                {"idcard": params.documento}
            )

            # Normaliza: pode vir como lista ou dict
            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            if not dados:
                return f"Nenhum condutor encontrado com o documento '{params.documento}'."

            linhas = ["🧑‍✈️ **Condutor Encontrado:**\n"]

            mapeamento = [
                (["name", "nombre"],                                   "Nome"),
                (["documento", "idcard", "cedula", "numero_documento"],"Documento"),
                (["phone", "telefono", "telefone"],                    "Telefone"),
                (["email", "correo"],                                  "E-mail"),
                # "licencia" é o campo espanhol para número da CNH/habilitação
                (["licencia", "license", "cnh", "numero_licencia"],    "Nº Habilitação / CNH"),
                (["expiration", "vencimiento", "validade_cnh"],        "Validade CNH"),
                (["grupo", "group", "grupo_conductor"],                "Grupo"),
                (["notes", "notas", "observaciones"],                  "Observações"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Status:** {formatar_ativo(dados)}")
            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_tickets
    # ENDPOINT: POST /gettickets
    # PARÂMETRO OPCIONAL: status (1 = aberto, 2 = fechado)
    # =========================================================================
    class TicketsInput(BaseModel):
        status: Optional[str] = Field(
            None,
            description=(
                "Filtro de status: 'aberto' para tickets em aberto, "
                "'fechado' para tickets encerrados. "
                "Deixe vazio (None) para listar todos os tickets."
            )
        )

    # Mapeamento de palavras em português para os valores numéricos da API
    # A API RedGPS usa 1 = aberto, 2 = fechado (documentação confirma)
    TICKET_STATUS_MAP = {
        "aberto":  "1",
        "open":    "1",
        "abierto": "1",
        "fechado": "2",
        "closed":  "2",
        "cerrado": "2",
    }

    @mcp.tool(name="listar_tickets")
    async def listar_tickets(params: TicketsInput) -> str:
        """
        Lista os tickets de suporte criados na plataforma, com filtro opcional por status.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Chamados ou tickets de suporte abertos
        - Ocorrências registradas
        - Status de atendimentos no sistema

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Liste os tickets abertos"
        - "Quais chamados estão em aberto?"
        - "Me mostra todos os tickets"
        - "Tem algum ticket fechado?"

        OUTROS ENDPOINTS RELACIONADOS (não implementados aqui mas disponíveis na API):
        - createticket → criar novo ticket
        - getTicketAnswer → ver detalhes e respostas de um ticket
        - createticketdetalle → responder um ticket
        """
        try:
            payload = {}
            if params.status:
                # Converte o texto em português para o código numérico da API
                status_val = TICKET_STATUS_MAP.get(
                    params.status.lower().strip(),
                    params.status  # passa o original se não reconhecido
                )
                payload["status"] = status_val

            # Documentação: POST /gettickets
            # Parâmetro opcional: status (1 ou 2)
            # Retorna lista de tickets com: id, titulo, descripcion, status, fecha
            tickets = await executar_post("gettickets", payload)

            if isinstance(tickets, dict):
                tickets = [tickets]

            if not tickets:
                status_txt = f" com status '{params.status}'" if params.status else ""
                return f"Nenhum ticket encontrado{status_txt}."

            linhas = [
                f"🎫 **Total de tickets: {len(tickets)}**\n",
                "| # | ID | Título | Status | Data de Criação |",
                "|---|----|--------|--------|-----------------|"
            ]

            for i, t in enumerate(tickets, 1):
                # A API RedGPS usa campos em espanhol: "titulo", "fecha", "descripcion"
                titulo = get_campo("titulo", "title", "subject", "asunto",        dados=t)
                status = get_campo("status", "estado",                             dados=t)
                # Datas podem vir como "fecha", "date" ou "fecha_creacion"
                data   = get_campo("fecha", "date", "created_at", "fecha_creacion", dados=t)
                id_t   = get_campo("id", "idticket",                               dados=t)
                linhas.append(f"| {i} | {id_t} | {titulo} | {status} | {data} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_modulos
    # ENDPOINT: POST /getModules
    # =========================================================================
    @mcp.tool(name="listar_modulos")
    async def listar_modulos() -> str:
        """
        Lista todos os módulos disponíveis na plataforma RedGPS.

        Os módulos definem as funcionalidades que podem ser atribuídas
        a usuários. Exemplo de módulos: Recorridos, Alertas, Reportes,
        Administración, Lugares.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quais módulos ou funcionalidades existem no sistema
        - Permissões ou recursos disponíveis
        - O que pode ser habilitado para um usuário

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Quais módulos existem no sistema?"
        - "Que funcionalidades estão disponíveis?"
        - "Lista os módulos do RedGPS"

        RESPOSTA ESPERADA DA API (exemplo real da documentação):
        [
          {"id": "2", "nombre": "Recorridos"},
          {"id": "3", "nombre": "Lugares"},
          {"id": "5", "nombre": "Alertas"},
          {"id": "8", "nombre": "Reportes"},
          {"id": "10", "nombre": "Administración"}
        ]
        """
        try:
            # Documentação: POST /getModules
            # Sem parâmetros extras além de apikey/token
            # A API retorna "nombre" em espanhol (confirmado na documentação oficial)
            modulos = await executar_post("getModules")

            if isinstance(modulos, dict):
                modulos = [modulos]

            if not modulos:
                return "Nenhum módulo encontrado."

            linhas = ["📦 **Módulos Disponíveis na Plataforma:**\n"]

            # Tradução dos nomes em espanhol para português
            # Adicionamos tradução para facilitar a leitura do usuário brasileiro
            traducoes = {
                "Recorridos":    "Percursos / Rotas",
                "Lugares":       "Locais / Pontos de Interesse",
                "Alertas":       "Alertas",
                "Reportes":      "Relatórios",
                "Administración":"Administração",
                "Conductores":   "Condutores",
                "Mantenimiento": "Manutenção",
                "Geocercas":     "Cercas Geográficas",
            }

            for m in modulos:
                # A API usa "nombre" (espanhol) como campo do nome do módulo
                nome_original = get_campo("nombre", "name", "module", "modulo", dados=m)
                id_m          = get_campo("id", "idmodule",                      dados=m)
                # Usa a tradução se disponível, senão mostra o original
                nome_exibido  = traducoes.get(nome_original, nome_original)
                linhas.append(f"- **{nome_exibido}** (ID: {id_m})")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)