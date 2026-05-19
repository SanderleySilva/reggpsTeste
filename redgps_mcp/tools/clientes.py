# tools/clientes.py
# Tools MCP relacionadas a Clientes, Usuários e Condutores

import asyncio

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional
from utils.api_client import post, tratar_erro


TIMEOUT_API = 15


async def executar_post(endpoint: str, payload: dict | None = None):
    """
    Executa chamadas à API com timeout e validação padrão.
    Centraliza o tratamento de status e timeout (padrão do veiculos.py).
    """
    resultado = await asyncio.wait_for(
        post(endpoint, payload),
        timeout=TIMEOUT_API
    )

    if resultado.get("status") != 200:
        raise Exception(
            f"API retornou status {resultado.get('status')}: {resultado}"
        )

    return resultado.get("data", {})


# ─── HELPERS DE CAMPO ─────────────────────────────────────────────────────────

def get_campo(*chaves, dados: dict, fallback: str = "N/A") -> str:
    """
    Tenta múltiplas chaves no dict e retorna o primeiro valor não vazio.
    Útil para lidar com a API que mescla campos em espanhol e inglês.
    """
    for chave in chaves:
        valor = dados.get(chave)
        if valor not in [None, "", 0, "0"]:
            return str(valor)
    return fallback


def formatar_ativo(dados: dict) -> str:
    """Retorna emoji de status ativo/inativo."""
    ativo = dados.get("active") or dados.get("activo") or dados.get("status")
    if ativo in [True, 1, "1", "true", "True"]:
        return "✅ Ativo"
    return "⛔ Inativo"


# ─── REGISTRO DAS TOOLS ───────────────────────────────────────────────────────

def registrar_tools_clientes(mcp: FastMCP):

    # ─── DADOS DO CLIENTE ─────────────────────────────────────────────────────
    @mcp.tool(name="dados_cliente")
    async def dados_cliente() -> str:
        """
        Retorna os dados detalhados do cliente/conta associado ao token atual.
        Use quando o usuário perguntar sobre os dados da sua conta, empresa ou perfil.
        """
        try:
            # A API RedGPS retorna dados do cliente dentro de getMyUser.
            # Tentamos getClientData primeiro; se falhar, usamos getMyUser como fallback.
            dados = {}
            try:
                dados = await executar_post("getClientData")
                # getClientData pode retornar lista ou dict
                if isinstance(dados, list):
                    dados = dados[0] if dados else {}
            except Exception:
                pass

            # Fallback: extrair dados do cliente via getMyUser
            if not dados:
                resultado_user = await asyncio.wait_for(
                    post("getMyUser"), timeout=TIMEOUT_API
                )
                user_data = resultado_user.get("data", {})
                # getMyUser embute dados do cliente em subcampo "client" ou no próprio dict
                dados = user_data.get("client") or user_data

            if not dados:
                return "Nenhum dado encontrado para este cliente."

            linhas = ["📄 **Dados do Cliente:**\n"]

            # Campos com suporte a nomes em espanhol e inglês
            mapeamento = [
                (["name", "nombre", "razonsocial"],          "Nome"),
                (["email", "correo"],                         "E-mail"),
                (["phone", "telefono", "telefone"],           "Telefone"),
                (["country", "pais"],                         "País"),
                (["city", "ciudad", "cidade"],                "Cidade"),
                (["address", "direccion", "endereco"],        "Endereço"),
                (["id", "idclient", "id_client"],             "ID do Cliente"),
                (["max_assets", "max_activos"],               "Máx. Ativos"),
                (["assets_count", "total_activos"],           "Total de Ativos"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Ativo:** {formatar_ativo(dados)}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── MEU USUÁRIO ──────────────────────────────────────────────────────────
    @mcp.tool(name="meu_usuario")
    async def meu_usuario() -> str:
        """
        Retorna as informações do usuário autenticado com o token atual.
        Use quando o usuário perguntar sobre seu próprio perfil, usuário ou conta.
        """
        try:
            dados = await executar_post("getMyUser")

            # getMyUser pode retornar lista ou dict
            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            if not dados:
                return "Nenhuma informação de usuário encontrada."

            linhas = ["👤 **Meu Usuário:**\n"]

            mapeamento = [
                (["username", "usuario", "login"],            "Usuário"),
                (["name", "nombre", "nome"],                  "Nome"),
                (["email", "correo"],                         "E-mail"),
                (["phone", "telefono", "telefone"],           "Telefone"),
                (["role", "perfil", "rol"],                   "Perfil"),
                (["idclient", "id_client", "idcliente"],      "ID do Cliente"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Ativo:** {formatar_ativo(dados)}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── LISTAR CLIENTES (nível distribuidor) ─────────────────────────────────
    @mcp.tool(name="listar_clientes")
    async def listar_clientes() -> str:
        """
        Lista todos os clientes cadastrados na plataforma (requer acesso nível distribuidor).
        Use quando o usuário perguntar sobre clientes, contas ou empresas cadastradas.
        """
        try:
            clientes = await executar_post("getClients")

            if isinstance(clientes, dict):
                clientes = [clientes]

            if not clientes:
                return "Nenhum cliente encontrado."

            linhas = [
                f"📋 **Total de clientes: {len(clientes)}**\n",
                "| # | Nome | ID | Status |",
                "|---|------|-----|--------|"
            ]

            for i, c in enumerate(clientes, 1):
                nome   = get_campo("name", "nombre", "razonsocial", dados=c)
                id_c   = get_campo("id", "idclient", "id_client",   dados=c)
                status = formatar_ativo(c)
                linhas.append(f"| {i} | {nome} | {id_c} | {status} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── LISTAR USUÁRIOS ──────────────────────────────────────────────────────
    class ListarUsuariosInput(BaseModel):
        id_cliente: Optional[str] = Field(
            None,
            description="ID do cliente para filtrar usuários. Deixe vazio para listar todos."
        )

    @mcp.tool(name="listar_usuarios")
    async def listar_usuarios(params: ListarUsuariosInput) -> str:
        """
        Lista os usuários de um cliente específico ou todos os usuários.
        Use quando o usuário perguntar sobre usuários cadastrados, logins ou acessos.
        """
        try:
            payload = {"idclient": params.id_cliente} if params.id_cliente else {}
            usuarios = await executar_post("getUsers", payload)

            if isinstance(usuarios, dict):
                usuarios = [usuarios]

            if not usuarios:
                return "Nenhum usuário encontrado."

            linhas = [
                f"👥 **Total de usuários: {len(usuarios)}**\n",
                "| # | Nome | Usuário | E-mail | Ativo |",
                "|---|------|---------|--------|-------|"
            ]

            for i, u in enumerate(usuarios, 1):
                nome     = get_campo("name", "nombre",    dados=u)
                username = get_campo("username", "usuario", "login", dados=u)
                email    = get_campo("email", "correo",   dados=u)
                ativo    = "✅" if u.get("active") or u.get("activo") else "⛔"
                linhas.append(f"| {i} | {nome} | {username} | {email} | {ativo} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── CONDUTORES ───────────────────────────────────────────────────────────
    @mcp.tool(name="listar_condutores")
    async def listar_condutores() -> str:
        """
        Lista todos os condutores cadastrados na plataforma.
        Use quando o usuário perguntar sobre condutores, motoristas ou drivers.
        """
        try:
            condutores = await executar_post("driverGetAll")

            if isinstance(condutores, dict):
                condutores = [condutores]

            if not condutores:
                return "Nenhum condutor encontrado."

            linhas = [
                f"🧑‍✈️ **Total de condutores: {len(condutores)}**\n",
                "| # | Nome | Documento | Telefone | Ativo |",
                "|---|------|-----------|----------|-------|"
            ]

            for i, c in enumerate(condutores, 1):
                nome  = get_campo("name", "nombre", dados=c)
                # A API RedGPS usa "documento", "idcard" ou "numero_documento"
                doc   = get_campo("documento", "idcard", "numero_documento", "cedula", dados=c)
                tel   = get_campo("phone", "telefono", "telefone", dados=c)
                ativo = "✅" if c.get("active") or c.get("activo") else "⛔"
                linhas.append(f"| {i} | {nome} | {doc} | {tel} | {ativo} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    class BuscarCondutorInput(BaseModel):
        documento: str = Field(
            ...,
            description="Número do documento/carteira de habilitação do condutor"
        )

    @mcp.tool(name="buscar_condutor")
    async def buscar_condutor(params: BuscarCondutorInput) -> str:
        """
        Busca informações de um condutor pelo número do documento/carteira de habilitação.
        Use quando o usuário perguntar sobre um motorista específico pelo documento.
        """
        try:
            dados = await executar_post(
                "getDriverByIdCard",
                {"idcard": params.documento}
            )

            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            if not dados:
                return f"Nenhum condutor encontrado com o documento '{params.documento}'."

            linhas = ["🧑‍✈️ **Condutor Encontrado:**\n"]

            mapeamento = [
                (["name", "nombre"],                                          "Nome"),
                (["documento", "idcard", "numero_documento", "cedula"],       "Documento"),
                (["phone", "telefono", "telefone"],                           "Telefone"),
                (["email", "correo"],                                         "E-mail"),
                # A API RedGPS usa "licencia" (espanhol) para CNH
                (["licencia", "license", "cnh", "numero_licencia"],           "CNH / Licença"),
                (["grupo", "group", "grupo_conductor"],                       "Grupo"),
            ]

            for chaves, label in mapeamento:
                valor = get_campo(*chaves, dados=dados)
                if valor != "N/A":
                    linhas.append(f"- **{label}:** {valor}")

            linhas.append(f"- **Ativo:** {formatar_ativo(dados)}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── TICKETS / SUPORTE ────────────────────────────────────────────────────
    class TicketsInput(BaseModel):
        status: Optional[str] = Field(
            None,
            description=(
                "Status do ticket: 'aberto' ou 'fechado'. "
                "Deixe vazio para listar todos."
            )
        )

    # Mapeamento de termos em português para os valores numéricos da API RedGPS
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
        Lista os tickets de suporte criados na plataforma.
        Use quando o usuário perguntar sobre tickets, chamados, suporte ou ocorrências.
        """
        try:
            payload = {}
            if params.status:
                # Converte "aberto"/"fechado" para o valor numérico esperado pela API
                status_val = TICKET_STATUS_MAP.get(
                    params.status.lower().strip(),
                    params.status  # passa o valor original se não reconhecido
                )
                payload["status"] = status_val

            tickets = await executar_post("gettickets", payload)

            if isinstance(tickets, dict):
                tickets = [tickets]

            if not tickets:
                return "Nenhum ticket encontrado."

            linhas = [
                f"🎫 **Total de tickets: {len(tickets)}**\n",
                "| # | ID | Título | Status | Data |",
                "|---|----|--------|--------|------|"
            ]

            for i, t in enumerate(tickets, 1):
                # A API RedGPS usa "titulo" e "descripcion" em espanhol
                titulo = get_campo("titulo", "title", "subject", "asunto", dados=t)
                status = get_campo("status", "estado",                      dados=t)
                # Datas podem vir como "fecha", "date" ou "created_at"
                data   = get_campo("fecha", "date", "created_at", "fecha_creacion", dados=t)
                id_t   = get_campo("id", "idticket",                        dados=t)
                linhas.append(f"| {i} | {id_t} | {titulo} | {status} | {data} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # ─── MÓDULOS DISPONÍVEIS ──────────────────────────────────────────────────
    @mcp.tool(name="listar_modulos")
    async def listar_modulos() -> str:
        """
        Lista todos os módulos disponíveis para atribuir a usuários na plataforma.
        Use quando o usuário perguntar sobre módulos, permissões ou funcionalidades disponíveis.
        """
        try:
            modulos = await executar_post("getModules")

            if isinstance(modulos, dict):
                modulos = [modulos]

            if not modulos:
                return "Nenhum módulo encontrado."

            linhas = ["📦 **Módulos Disponíveis:**\n"]

            for m in modulos:
                nome = get_campo("name", "nombre", "module", "modulo", dados=m)
                id_m = get_campo("id", "idmodule", dados=m)
                linhas.append(f"- **{nome}** (ID: {id_m})")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)