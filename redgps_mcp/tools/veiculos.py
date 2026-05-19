# tools/veiculos.py
# Tools MCP relacionadas a Veículos

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from utils.api_client import post, tratar_erro


def registrar_tools_veiculos(mcp: FastMCP):

    @mcp.tool(name="listar_veiculos")
    async def listar_veiculos() -> str:
        """
        Lista todos os veículos cadastrados e atribuídos ao usuário.
        Use quando o usuário perguntar sobre veículos, frota, ativos ou equipamentos GPS cadastrados.
        """
        try:
            resultado = await post("vehicleGetAll")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            veiculos = resultado.get("data", [])
            if not veiculos:
                return "Nenhum veículo encontrado na sua conta."
            linhas = [f"🚗 **Total de veículos: {len(veiculos)}**\n", "| # | Nome/Placa | ID | Ativo |", "|---|------------|----|-------|"]
            for i, v in enumerate(veiculos, 1):
                nome  = v.get("name") or v.get("plate") or "N/A"
                id_v  = v.get("id") or v.get("idasset") or "N/A"
                ativo = "✅" if v.get("active") or v.get("status") == 1 else "⛔"
                linhas.append(f"| {i} | {nome} | {id_v} | {ativo} |")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    @mcp.tool(name="listar_veiculos_completo")
    async def listar_veiculos_completo() -> str:
        """
        Lista todos os veículos com informações completas: marca, modelo, ano, cor, placa e sensores.
        Use quando precisar de detalhes técnicos dos veículos da frota.
        """
        try:
            resultado = await post("vehicleGetAllComplete")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            veiculos = resultado.get("data", [])
            if not veiculos:
                return "Nenhum veículo encontrado."
            linhas = [f"🚗 **Veículos — Informações Completas ({len(veiculos)} total)**\n"]
            for v in veiculos:
                nome   = v.get("name") or v.get("plate") or "N/A"
                marca  = v.get("brand") or "N/A"
                modelo = v.get("model") or "N/A"
                ano    = v.get("year") or "N/A"
                cor    = v.get("color") or "N/A"
                placa  = v.get("plate") or "N/A"
                linhas.append(f"---\n**{nome}**\n- Placa: {placa} | Marca: {marca} | Modelo: {modelo} | Ano: {ano} | Cor: {cor}")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    @mcp.tool(name="localizacao_veiculos")
    async def localizacao_veiculos() -> str:
        """
        Retorna a localização em tempo real de todos os veículos da frota.
        Use quando o usuário perguntar onde estão os veículos, localização, posição atual,
        velocidade, ignição, condutor ou último reporte dos rastreadores GPS.
        """
        try:
            resultado = await post("getdata")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            veiculos = resultado.get("data", [])
            if not veiculos:
                return "Nenhum dado de localização encontrado."
            linhas = [f"📡 **Localização em Tempo Real — {len(veiculos)} veículo(s)**\n"]
            for v in veiculos:
                nome       = v.get("name") or v.get("device") or "N/A"
                lat        = v.get("latitude", "N/A")
                lon        = v.get("longitude", "N/A")
                velocidade = v.get("speed", 0)
                ignicao    = v.get("ignition", 0)
                data       = v.get("date", "N/A")
                hora       = v.get("time", "N/A")
                geo        = v.get("geo") or v.get("address") or ""
                odometro   = v.get("odometer", "N/A")
                condutor   = v.get("driver") or "Não identificado"
                evento     = v.get("event") or "N/A"
                maps_url   = f"https://maps.google.com/?q={lat},{lon}" if lat != "N/A" else ""
                linhas.append(f"---\n**🚗 {nome}**")
                linhas.append(f"- Ignição: {'🔑 Ligado' if ignicao else '⭕ Desligado'}")
                linhas.append(f"- Velocidade: {velocidade} km/h | Evento: {evento}")
                linhas.append(f"- Condutor: {condutor} | Odômetro: {odometro} km")
                linhas.append(f"- Último reporte: {data} às {hora}")
                if geo:
                    linhas.append(f"- Local: {geo}")
                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    class BuscarVeiculoInput(BaseModel):
        nome_ou_placa: str = Field(..., description="Nome, placa ou identificador do veículo")

    @mcp.tool(name="buscar_veiculo")
    async def buscar_veiculo(params: BuscarVeiculoInput) -> str:
        """
        Busca um veículo específico pelo nome ou placa e retorna sua localização atual.
        Use quando o usuário perguntar sobre um veículo específico pelo nome ou placa.
        """
        try:
            resultado = await post("getdata")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            veiculos    = resultado.get("data", [])
            termo       = params.nome_ou_placa.lower()
            encontrados = [v for v in veiculos if termo in str(v.get("name", "")).lower() or termo in str(v.get("plate", "")).lower()]
            if not encontrados:
                return f"Nenhum veículo encontrado com '{params.nome_ou_placa}'."
            linhas = [f"🔍 **{len(encontrados)} veículo(s) encontrado(s):**\n"]
            for v in encontrados:
                nome       = v.get("name") or v.get("device") or "N/A"
                lat        = v.get("latitude", "N/A")
                lon        = v.get("longitude", "N/A")
                velocidade = v.get("speed", 0)
                ignicao    = v.get("ignition", 0)
                data       = v.get("date", "N/A")
                hora       = v.get("time", "N/A")
                geo        = v.get("geo") or v.get("address") or ""
                maps_url   = f"https://maps.google.com/?q={lat},{lon}" if lat != "N/A" else ""
                linhas.append(f"**🚗 {nome}**")
                linhas.append(f"- Ignição: {'🔑 Ligado' if ignicao else '⭕ Desligado'} | Velocidade: {velocidade} km/h")
                linhas.append(f"- Último reporte: {data} às {hora}")
                if geo:
                    linhas.append(f"- Local: {geo}")
                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    class OdometroInput(BaseModel):
        id_veiculo: str = Field(..., description="ID do veículo para consultar o odômetro")

    @mcp.tool(name="consultar_odometro")
    async def consultar_odometro(params: OdometroInput) -> str:
        """
        Consulta o odômetro de um veículo específico pelo ID.
        Use quando o usuário perguntar sobre quilometragem, km rodados ou odômetro.
        """
        try:
            resultado = await post("getOdometer", {"idasset": params.id_veiculo})
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            dados = resultado.get("data", {})
            return f"🔢 **Odômetro do veículo {params.id_veiculo}:**\n- Total: {dados.get('odometer', 'N/A')} km"
        except Exception as e:
            return tratar_erro(e)


    class HistoricoEventosInput(BaseModel):
        id_veiculo: str  = Field(..., description="ID do veículo")
        data_inicio: str = Field(..., description="Data início (YYYY-MM-DD)")
        data_fim: str    = Field(..., description="Data fim (YYYY-MM-DD)")

    @mcp.tool(name="historico_eventos")
    async def historico_eventos(params: HistoricoEventosInput) -> str:
        """
        Consulta o histórico de eventos (alertas, paradas, ignição) de um veículo em um período.
        Use quando o usuário perguntar sobre eventos, alertas ou histórico de um veículo.
        """
        try:
            resultado = await post("historyGetEvents", {
                "idasset": params.id_veiculo,
                "date_begin": params.data_inicio,
                "date_end": params.data_fim,
            })
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            eventos = resultado.get("data", [])
            if not eventos:
                return f"Nenhum evento encontrado para o período {params.data_inicio} a {params.data_fim}."
            linhas = [f"📋 **Histórico de Eventos — {len(eventos)} evento(s)**\n"]
            for e in eventos[:50]:
                linhas.append(f"- {e.get('date')} {e.get('time')} | {e.get('event', 'N/A')} | Vel: {e.get('speed', 0)} km/h")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    class HistoricoPosicaoInput(BaseModel):
        id_veiculo: str  = Field(..., description="ID do veículo")
        data_inicio: str = Field(..., description="Data/hora início (YYYY-MM-DD HH:MM:SS)")
        data_fim: str    = Field(..., description="Data/hora fim (YYYY-MM-DD HH:MM:SS)")

    @mcp.tool(name="historico_posicoes")
    async def historico_posicoes(params: HistoricoPosicaoInput) -> str:
        """
        Consulta o histórico de posições GPS de um veículo em um período de tempo.
        Use quando o usuário perguntar sobre rota percorrida, trajeto ou posições históricas.
        """
        try:
            resultado = await post("historyGet", {
                "idasset": params.id_veiculo,
                "date_begin": params.data_inicio,
                "date_end": params.data_fim,
            })
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            posicoes = resultado.get("data", [])
            if not posicoes:
                return "Nenhuma posição encontrada para o período informado."
            linhas = [f"📍 **Histórico de Posições — {len(posicoes)} registro(s)**\n"]
            for p in posicoes[:50]:
                lat = p.get("latitude", "N/A")
                lon = p.get("longitude", "N/A")
                linhas.append(f"- {p.get('date')} {p.get('time')} | Vel: {p.get('speed', 0)} km/h | [{lat}, {lon}]")
            if len(posicoes) > 50:
                linhas.append(f"\n_... e mais {len(posicoes) - 50} registros._")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)


    @mcp.tool(name="listar_marcas_modelos")
    async def listar_marcas_modelos() -> str:
        """
        Lista todas as marcas e modelos de veículos disponíveis na plataforma.
        Use quando o usuário perguntar sobre marcas ou modelos disponíveis.
        """
        try:
            resultado = await post("getBrandsAndModels")
            if resultado.get("status") != 200:
                return f"⚠️ API retornou status {resultado.get('status')}: {resultado}"
            dados  = resultado.get("data", [])
            linhas = ["🚘 **Marcas e Modelos Disponíveis:**\n"]
            for marca in dados[:30]:
                nome    = marca.get("name") or marca.get("brand") or "N/A"
                modelos = marca.get("models") or []
                linhas.append(f"**{nome}**: {', '.join([m.get('name', '') for m in modelos[:5]])}")
            return "\n".join(linhas)
        except Exception as e:
            return tratar_erro(e)