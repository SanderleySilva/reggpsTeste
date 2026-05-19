# tools/clientes.py
# Tools MCP relacionadas a Clientes, Usuários e Condutores

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional
from utils.api_client import post, tratar_erro


def registrar_tools_clientes(mcp: FastMCP):

    # ─── DADOS DO CLIENTE ─────────────────────────────────────────────────────
    @mcp.tool(name="dados_cliente")
    async def dados_cliente() -> str:
        """
        Retorna os dados detalhados do cliente/conta associado ao token atual.
        Use quando o usuário perguntar sobre os dados da sua conta, empresa ou perfil.
        """
        try:
            resultado = await post("getClientData")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            dados  = resultado.get("data", {})
            if not dados:
                return "Nenhum dado encontrado para este cliente."
            linhas = ["📄 **Dados do Cliente:**\n"]
            campos = {"name": "Nome", "email": "E-mail", "phone": "Telefone", "country": "País",
                      "city": "Cidade", "address": "Endereço", "active": "Ativo",
                      "id": "ID", "idclient": "ID do Cliente", "max_assets": "Máx. Ativos", "assets_count": "Total de Ativos"}
            for chave, label in campos.items():
                if chave in dados:
                    valor = dados[chave]
                    if chave == "active":
                        valor = "✅ Sim" if valor else "❌ Não"
                    linhas.append(f"- **{label}:** {valor}")
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
            resultado = await post("getMyUser")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            dados  = resultado.get("data", {})
            if not dados:
                return "Nenhuma informação de usuário encontrada."
            linhas = ["👤 **Meu Usuário:**\n"]
            campos = {"username": "Usuário", "name": "Nome", "email": "E-mail",
                      "phone": "Telefone", "role": "Perfil", "active": "Ativo", "idclient": "ID do Cliente"}
            for chave, label in campos.items():
                if chave in dados:
                    valor = dados[chave]
                    if chave == "active":
                        valor = "✅ Sim" if valor else "❌ Não"
                    linhas.append(f"- **{label}:** {valor}")
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
            resultado = await post("getClients")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            clientes = resultado.get("data", [])
            if not clientes:
                return "Nenhum cliente encontrado."
            linhas = [f"📋 **Total de clientes: {len(clientes)}**\n", "| # | Nome | ID | Status |", "|---|------|----|--------|"]
            for i, c in enumerate(clientes, 1):
                nome   = c.get("name") or c.get("nombre") or "N/A"
                id_c   = c.get("id") or c.get("idclient") or "N/A"
                status = "✅ Ativo" if c.get("active") or c.get("status") == 1 else "⛔ Inativo"
                linhas.append(f"| {i} | {nome} | {id_c} | {status} |")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    # ─── LISTAR USUÁRIOS ──────────────────────────────────────────────────────
    class ListarUsuariosInput(BaseModel):
        id_cliente: Optional[str] = Field(None, description="ID do cliente para filtrar usuários. Deixe vazio para listar todos.")

    @mcp.tool(name="listar_usuarios")
    async def listar_usuarios(params: ListarUsuariosInput) -> str:
        """
        Lista os usuários de um cliente específico ou todos os usuários.
        Use quando o usuário perguntar sobre usuários cadastrados, logins ou acessos.
        """
        try:
            extra = {"idclient": params.id_cliente} if params.id_cliente else {}
            resultado = await post("getUsers", extra)
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            usuarios = resultado.get("data", [])
            if not usuarios:
                return "Nenhum usuário encontrado."
            linhas = [f"👥 **Total de usuários: {len(usuarios)}**\n", "| # | Nome | Usuário | E-mail | Ativo |", "|---|------|---------|--------|-------|"]
            for i, u in enumerate(usuarios, 1):
                nome     = u.get("name") or "N/A"
                username = u.get("username") or "N/A"
                email    = u.get("email") or "N/A"
                ativo    = "✅" if u.get("active") else "⛔"
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
            resultado = await post("driverGetAll")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            condutores = resultado.get("data", [])
            if not condutores:
                return "Nenhum condutor encontrado."
            linhas = [f"🧑‍✈️ **Total de condutores: {len(condutores)}**\n", "| # | Nome | Documento | Ativo |", "|---|------|-----------|-------|"]
            for i, c in enumerate(condutores, 1):
                nome     = c.get("name") or c.get("nombre") or "N/A"
                doc      = c.get("idcard") or c.get("document") or "N/A"
                ativo    = "✅" if c.get("active") else "⛔"
                linhas.append(f"| {i} | {nome} | {doc} | {ativo} |")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    class BuscarCondutorInput(BaseModel):
        documento: str = Field(..., description="Número do documento/carteira do condutor")

    @mcp.tool(name="buscar_condutor")
    async def buscar_condutor(params: BuscarCondutorInput) -> str:
        """
        Busca informações de um condutor pelo número do documento/carteira de habilitação.
        Use quando o usuário perguntar sobre um motorista específico pelo documento.
        """
        try:
            resultado = await post("getDriverByIdCard", {"idcard": params.documento})
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            dados  = resultado.get("data", {})
            if not dados:
                return f"Nenhum condutor encontrado com o documento '{params.documento}'."
            linhas = ["🧑‍✈️ **Condutor Encontrado:**\n"]
            campos = {"name": "Nome", "idcard": "Documento", "phone": "Telefone",
                      "email": "E-mail", "license": "CNH", "active": "Ativo"}
            for chave, label in campos.items():
                if chave in dados:
                    valor = dados[chave]
                    if chave == "active":
                        valor = "✅ Sim" if valor else "❌ Não"
                    linhas.append(f"- **{label}:** {valor}")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    # ─── TICKETS / SUPORTE ────────────────────────────────────────────────────
    class TicketsInput(BaseModel):
        status: Optional[str] = Field(None, description="Status do ticket: aberto, fechado. Deixe vazio para todos.")

    @mcp.tool(name="listar_tickets")
    async def listar_tickets(params: TicketsInput) -> str:
        """
        Lista os tickets de suporte criados na plataforma.
        Use quando o usuário perguntar sobre tickets, chamados, suporte ou ocorrências.
        """
        try:
            extra    = {"status": params.status} if params.status else {}
            resultado = await post("gettickets", extra)
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            tickets = resultado.get("data", [])
            if not tickets:
                return "Nenhum ticket encontrado."
            linhas = [f"🎫 **Total de tickets: {len(tickets)}**\n", "| # | ID | Título | Status | Data |", "|---|----|-|-------|------|"]
            for i, t in enumerate(tickets, 1):
                titulo = t.get("title") or t.get("subject") or "N/A"
                status = t.get("status") or "N/A"
                data   = t.get("date") or t.get("created_at") or "N/A"
                id_t   = t.get("id") or "N/A"
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
            resultado = await post("getModules")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            modulos = resultado.get("data", [])
            if not modulos:
                return "Nenhum módulo encontrado."
            linhas = ["📦 **Módulos Disponíveis:**\n"]
            for m in modulos:
                nome = m.get("name") or m.get("module") or "N/A"
                id_m = m.get("id") or "N/A"
                linhas.append(f"- **{nome}** (ID: {id_m})")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)