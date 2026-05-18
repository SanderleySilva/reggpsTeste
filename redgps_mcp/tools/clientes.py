# tools/clientes.py

from mcp.server.fastmcp import FastMCP
from utils.api_client import post, tratar_erro
import json


def formatar_valor(valor):
    if isinstance(valor, bool):
        return "✅ Sim" if valor else "❌ Não"

    if valor is None:
        return "N/A"

    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, indent=2)

    return str(valor)


def gerar_markdown_objeto(obj: dict, titulo: str):
    linhas = [f"## {titulo}\n"]

    for chave, valor in obj.items():
        linhas.append(f"- **{chave}:** {formatar_valor(valor)}")

    return "\n".join(linhas)


def registrar_tools_clientes(mcp: FastMCP):

    @mcp.tool(name="listar_clientes")
    async def listar_clientes(
        incluir_json_completo: bool = False
    ) -> str:
        """
        Lista todos os clientes cadastrados na plataforma RedGPS.

        Args:
            incluir_json_completo:
                Se True, retorna também todos os campos completos da API.
        """

        try:
            resultado = await post("getClients")

            if resultado.get("status") != 200:
                return (
                    f"⚠️ API retornou status "
                    f"{resultado.get('status')}\n\n"
                    f"{json.dumps(resultado, indent=2, ensure_ascii=False)}"
                )

            clientes = resultado.get("data", [])

            if not clientes:
                return "Nenhum cliente encontrado."

            linhas = [
                f"# 📋 Clientes encontrados: {len(clientes)}\n"
            ]

            for i, cliente in enumerate(clientes, 1):

                nome = (
                    cliente.get("name")
                    or cliente.get("nombre")
                    or cliente.get("client_name")
                    or "N/A"
                )

                id_cliente = (
                    cliente.get("id")
                    or cliente.get("idclient")
                    or "N/A"
                )

                ativo = (
                    cliente.get("active") is True
                    or cliente.get("status") == 1
                )

                status = "✅ Ativo" if ativo else "⛔ Inativo"

                linhas.extend([
                    f"## Cliente {i}",
                    f"- **Nome:** {nome}",
                    f"- **ID:** {id_cliente}",
                    f"- **Status:** {status}",
                ])

                # Retorna TODOS os campos disponíveis
                if incluir_json_completo:
                    linhas.append("\n### JSON Completo")
                    linhas.append("```json")
                    linhas.append(
                        json.dumps(
                            cliente,
                            indent=2,
                            ensure_ascii=False
                        )
                    )
                    linhas.append("```")

                linhas.append("")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    @mcp.tool(name="dados_cliente")
    async def dados_cliente(
        incluir_json_completo: bool = True
    ) -> str:
        """
        Retorna todos os dados detalhados do cliente atual.
        """

        try:
            resultado = await post("getClientData")

            if resultado.get("status") != 200:
                return (
                    f"⚠️ API retornou status "
                    f"{resultado.get('status')}\n\n"
                    f"{json.dumps(resultado, indent=2, ensure_ascii=False)}"
                )

            dados = resultado.get("data", {})

            if not dados:
                return "Nenhum dado encontrado."

            resposta = gerar_markdown_objeto(
                dados,
                "📄 Dados do Cliente"
            )

            if incluir_json_completo:
                resposta += "\n\n## JSON Completo\n```json\n"
                resposta += json.dumps(
                    dados,
                    indent=2,
                    ensure_ascii=False
                )
                resposta += "\n```"

            return resposta

        except Exception as e:
            return tratar_erro(e)

    @mcp.tool(name="meu_usuario")
    async def meu_usuario(
        incluir_json_completo: bool = True
    ) -> str:
        """
        Retorna todas as informações do usuário autenticado.
        """

        try:
            resultado = await post("getMyUser")

            if resultado.get("status") != 200:
                return (
                    f"⚠️ API retornou status "
                    f"{resultado.get('status')}\n\n"
                    f"{json.dumps(resultado, indent=2, ensure_ascii=False)}"
                )

            dados = resultado.get("data", {})

            if not dados:
                return "Nenhuma informação encontrada."

            resposta = gerar_markdown_objeto(
                dados,
                "👤 Meu Usuário"
            )

            if incluir_json_completo:
                resposta += "\n\n## JSON Completo\n```json\n"
                resposta += json.dumps(
                    dados,
                    indent=2,
                    ensure_ascii=False
                )
                resposta += "\n```"

            return resposta

        except Exception as e:
            return tratar_erro(e)

    @mcp.tool(name="consultar_endpoint_clientes")
    async def consultar_endpoint_clientes(
        endpoint: str,
        payload: dict = {}
    ) -> str:
        """
        Consulta qualquer endpoint relacionado a clientes.

        Exemplos:
        - getClients
        - getClientData
        - getMyUser
        """

        try:
            resultado = await post(endpoint, payload)

            return json.dumps(
                resultado,
                indent=2,
                ensure_ascii=False
            )

        except Exception as e:
            return tratar_erro(e)