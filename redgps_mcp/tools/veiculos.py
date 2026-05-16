# tools/veiculos.py
# Tools MCP relacionadas a Veículos

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional
from utils.api_client import post, tratar_erro


def registrar_tools_veiculos(mcp: FastMCP):

    @mcp.tool(name="listar_veiculos")
    async def listar_veiculos() -> str:
        """
        Lista todos os veículos/ativos cadastrados e atribuídos ao usuário.
        Use quando o usuário perguntar sobre veículos, frota, ativos ou equipamentos GPS cadastrados.
        """
        try:
            resultado = await post("vehicleGetAll")

            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"

            veiculos = resultado.get("data", [])
            if not veiculos:
                return "Nenhum veículo encontrado na sua conta."

            linhas = [
                f"🚗 **Total de veículos: {len(veiculos)}**\n",
                "| # | Nome/Placa | ID | Ativo |",
                "|---|------------|----|-------|"
            ]
            for i, v in enumerate(veiculos, 1):
                nome   = v.get("name") or v.get("nombre") or v.get("plate") or "N/A"
                id_v   = v.get("id") or v.get("idasset") or "N/A"
                ativo  = "✅ Sim" if v.get("active") or v.get("status") == 1 else "⛔ Não"
                linhas.append(f"| {i} | {nome} | {id_v} | {ativo} |")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    @mcp.tool(name="localizacao_veiculos")
    async def localizacao_veiculos() -> str:
        """
        Retorna a localização em tempo real e dados atuais de todos os veículos da frota.
        Use quando o usuário perguntar onde estão os veículos, localização, posição atual,
        velocidade, ignição ou último reporte dos rastreadores GPS.
        """
        try:
            resultado = await post("getdata")

            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"

            veiculos = resultado.get("data", [])
            if not veiculos:
                return "Nenhum dado de localização encontrado."

            linhas = [
                f"📡 **Localização em Tempo Real — {len(veiculos)} veículo(s)**\n"
            ]

            for v in veiculos:
                nome      = v.get("name") or v.get("nombre") or v.get("device") or "N/A"
                lat       = v.get("latitude", "N/A")
                lon       = v.get("longitude", "N/A")
                velocidade= v.get("speed", 0)
                ignicao   = v.get("ignition", 0)
                data      = v.get("date", "N/A")
                hora      = v.get("time", "N/A")
                geo       = v.get("geo") or v.get("geocerca") or ""

                ignicao_icon = "🔑 Ligado" if ignicao else "⭕ Desligado"
                vel_txt      = f"{velocidade} km/h" if velocidade else "Parado"
                maps_url     = f"https://maps.google.com/?q={lat},{lon}" if lat != "N/A" else ""

                linhas.append(f"---")
                linhas.append(f"**🚗 {nome}**")
                linhas.append(f"- Ignição: {ignicao_icon}")
                linhas.append(f"- Velocidade: {vel_txt}")
                linhas.append(f"- Último reporte: {data} às {hora}")
                if geo:
                    linhas.append(f"- Local: {geo}")
                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    class BuscarVeiculoInput(BaseModel):
        nome_ou_placa: str = Field(
            ...,
            description="Nome, placa ou identificador do veículo a buscar"
        )

    @mcp.tool(name="buscar_veiculo")
    async def buscar_veiculo(params: BuscarVeiculoInput) -> str:
        """
        Busca um veículo específico pelo nome ou placa e retorna sua localização atual.
        Use quando o usuário perguntar sobre um veículo específico pelo nome ou placa.
        """
        try:
            # Busca todos e filtra localmente
            resultado = await post("getdata")

            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"

            veiculos = resultado.get("data", [])
            termo    = params.nome_ou_placa.lower()

            encontrados = [
                v for v in veiculos
                if termo in str(v.get("name", "")).lower()
                or termo in str(v.get("nombre", "")).lower()
                or termo in str(v.get("plate", "")).lower()
                or termo in str(v.get("device", "")).lower()
            ]

            if not encontrados:
                return f"Nenhum veículo encontrado com '{params.nome_ou_placa}'."

            linhas = [f"🔍 **{len(encontrados)} veículo(s) encontrado(s) para '{params.nome_ou_placa}':**\n"]

            for v in encontrados:
                nome      = v.get("name") or v.get("nombre") or v.get("device") or "N/A"
                lat       = v.get("latitude", "N/A")
                lon       = v.get("longitude", "N/A")
                velocidade= v.get("speed", 0)
                ignicao   = v.get("ignition", 0)
                data      = v.get("date", "N/A")
                hora      = v.get("time", "N/A")
                geo       = v.get("geo") or ""
                maps_url  = f"https://maps.google.com/?q={lat},{lon}" if lat != "N/A" else ""

                linhas.append(f"**🚗 {nome}**")
                linhas.append(f"- Ignição: {'🔑 Ligado' if ignicao else '⭕ Desligado'}")
                linhas.append(f"- Velocidade: {velocidade} km/h")
                linhas.append(f"- Último reporte: {data} às {hora}")
                if geo:
                    linhas.append(f"- Local: {geo}")
                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)
