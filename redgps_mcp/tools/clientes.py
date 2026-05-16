# tools/clientes.py
# Tools MCP relacionadas a Clientes

from mcp.server.fastmcp import FastMCP
from utils.api_client import post, tratar_erro


def registrar_tools_clientes(mcp: FastMCP):

    @mcp.tool(name="listar_clientes")
    async def listar_clientes() -> str:
        """
        Lista todos os clientes cadastrados na plataforma RedGPS.
        Use quando o usuário perguntar sobre clientes, contas ou empresas cadastradas.
        """
        try:
            resultado = await post("getClients")

            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"

            clientes = resultado.get("data", [])
            if not clientes:
                return "Nenhum cliente encontrado."

            linhas = [
                f"📋 **Total de clientes: {len(clientes)}**\n",
                "| # | Nome | ID | Status |",
                "|---|------|----|--------|"
            ]
            for i, c in enumerate(clientes, 1):
                nome   = c.get("name") or c.get("nombre") or c.get("client_name") or "N/A"
                id_c   = c.get("id") or c.get("idclient") or "N/A"
                status = "✅ Ativo" if c.get("active") or c.get("status") == 1 else "⛔ Inativo"
                linhas.append(f"| {i} | {nome} | {id_c} | {status} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


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

            dados = resultado.get("data", {})
            if not dados:
                return "Nenhum dado encontrado para este cliente."

            # Formata os campos disponíveis de forma legível
            linhas = ["📄 **Dados do Cliente:**\n"]
            campos_legíveis = {
                "name": "Nome",
                "nombre": "Nome",
                "email": "E-mail",
                "phone": "Telefone",
                "country": "País",
                "city": "Cidade",
                "address": "Endereço",
                "active": "Ativo",
                "status": "Status",
                "id": "ID",
                "idclient": "ID do Cliente",
                "max_assets": "Máx. Ativos",
                "assets_count": "Total de Ativos",
            }
            for chave, label in campos_legíveis.items():
                if chave in dados:
                    valor = dados[chave]
                    if isinstance(valor, bool) or chave == "active":
                        valor = "✅ Sim" if valor else "❌ Não"
                    linhas.append(f"- **{label}:** {valor}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


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

            dados = resultado.get("data", {})
            if not dados:
                return "Nenhuma informação de usuário encontrada."

            linhas = ["👤 **Meu Usuário:**\n"]
            campos = {
                "username": "Usuário",
                "name": "Nome",
                "email": "E-mail",
                "phone": "Telefone",
                "role": "Perfil/Role",
                "active": "Ativo",
                "idclient": "ID do Cliente",
            }
            for chave, label in campos.items():
                if chave in dados:
                    valor = dados[chave]
                    if chave == "active":
                        valor = "✅ Sim" if valor else "❌ Não"
                    linhas.append(f"- **{label}:** {valor}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)
