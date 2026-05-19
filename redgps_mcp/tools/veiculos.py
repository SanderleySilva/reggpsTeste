# tools/veiculos.py
# Tools MCP relacionadas a Veículos

from datetime import datetime
from typing import Any, Dict, List

import asyncio

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

from utils.api_client import post, tratar_erro


# =========================================================
# HELPERS
# =========================================================

TIMEOUT_API = 15
MAX_REGISTROS = 50
MAX_VEICULOS = 100


async def executar_post(endpoint: str, payload: Dict[str, Any] | None = None):
    """
    Executa chamadas à API com timeout e validação padrão.
    """
    resultado = await asyncio.wait_for(
        post(endpoint, payload),
        timeout=TIMEOUT_API
    )

    if resultado.get("status") != 200:
        raise Exception(
            f"API retornou status {resultado.get('status')}: {resultado}"
        )

    return resultado.get("data", [])


def gerar_maps_url(lat, lon) -> str:
    """
    Gera URL do Google Maps apenas se latitude/longitude forem válidas.
    """
    if lat in [None, "", "N/A"] or lon in [None, "", "N/A"]:
        return ""

    return f"https://maps.google.com/?q={lat},{lon}"


def status_ativo(veiculo: Dict[str, Any]) -> str:
    """
    Determina status ativo do veículo.
    """
    try:
        status = int(veiculo.get("status", 0))
        return "✅" if status == 1 else "⛔"
    except Exception:
        return "⛔"


def limitar_lista(lista: List[Any], limite: int):
    """
    Limita quantidade de registros.
    """
    return lista[:limite]


def get_nome_veiculo(v: Dict[str, Any]) -> str:
    """
    Retorna o nome/identificação do veículo tentando múltiplos campos.
    A API RedGPS usa campos em espanhol: 'nombre', 'patente', 'name', 'plate', 'device'.
    """
    return (
        v.get("nombre")        # vehicleGetAll
        or v.get("name")       # getdata
        or v.get("patente")    # vehicleGetAll (placa)
        or v.get("plate")      # getdata
        or v.get("device")     # getdata (fallback)
        or "N/A"
    )


def get_placa(v: Dict[str, Any]) -> str:
    """
    Retorna a placa tentando campos em espanhol e inglês.
    """
    return v.get("patente") or v.get("plate") or "N/A"


def get_marca(v: Dict[str, Any]) -> str:
    """
    Retorna a marca do veículo.
    """
    return v.get("marca") or v.get("brand") or "N/A"


def get_modelo(v: Dict[str, Any]) -> str:
    """
    Retorna o modelo do veículo.
    """
    return v.get("modelo") or v.get("model") or "N/A"


def get_ano(v: Dict[str, Any]) -> str:
    """
    Retorna o ano do veículo. '0' é tratado como não informado.
    """
    ano = v.get("anio") or v.get("year") or "N/A"
    return "N/A" if str(ano) == "0" else str(ano)


def get_cor(v: Dict[str, Any]) -> str:
    """
    Retorna a cor do veículo.
    """
    return v.get("color") or "N/A"


def get_id_veiculo(v: Dict[str, Any]) -> str:
    """
    Retorna o ID do veículo tentando múltiplos campos.
    """
    return (
        str(v.get("id") or "")
        or str(v.get("idasset") or "")
        or str(v.get("asset") or "")
        or "N/A"
    )


def get_condutor(v: Dict[str, Any]) -> str:
    """
    Retorna o condutor (campo em espanhol ou inglês).
    """
    return v.get("conductor") or v.get("driver") or "Não identificado"


def get_grupo(v: Dict[str, Any]) -> str:
    """
    Retorna o grupo do veículo.
    """
    return v.get("grupo") or v.get("group") or "N/A"


def get_tipo(v: Dict[str, Any]) -> str:
    """
    Retorna o tipo do veículo.
    """
    return v.get("tipo_vehiculo") or v.get("type") or "N/A"


# =========================================================
# VALIDADORES
# =========================================================

class BuscarVeiculoInput(BaseModel):
    nome_ou_placa: str = Field(
        ...,
        description="Nome, placa ou identificador do veículo"
    )

    @field_validator("nome_ou_placa")
    @classmethod
    def validar_nome(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Informe um nome ou placa válida.")

        return value


class OdometroInput(BaseModel):
    id_veiculo: str = Field(
        ...,
        description="ID do veículo para consultar o odômetro"
    )


class HistoricoEventosInput(BaseModel):
    id_veiculo: str = Field(..., description="ID do veículo")
    data_inicio: str = Field(..., description="Data início YYYY-MM-DD")
    data_fim: str = Field(..., description="Data fim YYYY-MM-DD")

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def validar_data(cls, value):
        datetime.strptime(value, "%Y-%m-%d")
        return value


class HistoricoPosicaoInput(BaseModel):
    id_veiculo: str = Field(..., description="ID do veículo")

    data_inicio: str = Field(
        ...,
        description="Data/hora início YYYY-MM-DD HH:MM:SS"
    )

    data_fim: str = Field(
        ...,
        description="Data/hora fim YYYY-MM-DD HH:MM:SS"
    )

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def validar_data_hora(cls, value):
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return value


# =========================================================
# REGISTRO DAS TOOLS
# =========================================================

def registrar_tools_veiculos(mcp: FastMCP):

    # =====================================================
    # LISTAR VEÍCULOS
    # =====================================================

    @mcp.tool(name="listar_veiculos")
    async def listar_veiculos() -> str:
        """
        Lista todos os veículos cadastrados e atribuídos ao usuário.
        Use quando o usuário perguntar sobre veículos, frota, ativos ou equipamentos GPS cadastrados.
        """

        try:
            veiculos = await executar_post("vehicleGetAll")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [
                f"🚗 **Total de veículos: {len(veiculos)}**\n",
                "| # | Nome | Placa | ID | Tipo | Grupo | Ativo |",
                "|---|---|---|---|---|---|---|"
            ]

            for i, v in enumerate(
                limitar_lista(veiculos, MAX_VEICULOS),
                start=1
            ):
                nome  = get_nome_veiculo(v)
                placa = get_placa(v)
                id_v  = get_id_veiculo(v)
                tipo  = get_tipo(v)
                grupo = get_grupo(v)
                ativo = status_ativo(v)

                linhas.append(
                    f"| {i} | {nome} | {placa} | {id_v} | {tipo} | {grupo} | {ativo} |"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # LISTAR VEÍCULOS COMPLETO
    # =====================================================

    @mcp.tool(name="listar_veiculos_completo")
    async def listar_veiculos_completo() -> str:
        """
        Lista veículos com detalhes completos: marca, modelo, ano, cor, placa e sensores.
        Use quando precisar de detalhes técnicos dos veículos da frota.
        """

        try:
            veiculos = await executar_post("vehicleGetAllComplete")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [
                f"🚗 **Veículos — Informações Completas ({len(veiculos)} total)**\n"
            ]

            for v in limitar_lista(veiculos, MAX_VEICULOS):
                nome     = get_nome_veiculo(v)
                placa    = get_placa(v)
                marca    = get_marca(v)
                modelo   = get_modelo(v)
                ano      = get_ano(v)
                cor      = get_cor(v)
                id_v     = get_id_veiculo(v)
                condutor = get_condutor(v)
                grupo    = get_grupo(v)
                tipo     = get_tipo(v)
                ativo    = status_ativo(v)

                bloco = [
                    "---",
                    f"**🚗 {nome}**",
                    f"- ID: {id_v}",
                    f"- Placa: {placa}",
                    f"- Marca: {marca}",
                    f"- Modelo: {modelo}",
                    f"- Ano: {ano}",
                    f"- Cor: {cor}",
                    f"- Tipo: {tipo}",
                    f"- Grupo: {grupo}",
                    f"- Condutor: {condutor}",
                    f"- Status: {ativo}",
                ]

                # Sensores (se existirem)
                sensores = v.get("sensors") or v.get("sensores")
                if sensores and isinstance(sensores, dict):
                    nomes_sensores = [
                        s.get("name") or k
                        for k, s in sensores.items()
                        if isinstance(s, dict) and (s.get("name") or k)
                    ]
                    if nomes_sensores:
                        bloco.append(f"- Sensores: {', '.join(nomes_sensores[:5])}")

                linhas.extend(bloco)

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # LOCALIZAÇÃO DOS VEÍCULOS
    # =====================================================

    @mcp.tool(name="localizacao_veiculos")
    async def localizacao_veiculos() -> str:
        """
        Retorna a localização em tempo real de todos os veículos da frota.
        Use quando o usuário perguntar onde estão os veículos, localização, posição atual,
        velocidade, ignição, condutor ou último reporte dos rastreadores GPS.
        """

        try:
            veiculos = await executar_post("getdata")

            if not veiculos:
                return "Nenhum dado de localização encontrado."

            linhas = [
                f"📡 **Localização em Tempo Real — {len(veiculos)} veículo(s)**\n"
            ]

            for v in limitar_lista(veiculos, MAX_VEICULOS):
                nome  = get_nome_veiculo(v)
                placa = get_placa(v)

                lat = v.get("latitude")
                lon = v.get("longitude")

                velocidade = v.get("speed", 0)
                ignicao    = "🔑 Ligado" if v.get("ignition") else "⭕ Desligado"
                condutor   = get_condutor(v)

                # Endereço: tenta 'geo', 'address', 'endereco'
                geo = (
                    v.get("geo")
                    or v.get("address")
                    or v.get("endereco")
                    or "Local não informado"
                )

                odometro = v.get("odometer") or v.get("odometro") or "N/A"
                evento   = v.get("event") or v.get("evento") or "N/A"

                data_rep = v.get("date") or v.get("fecha") or "N/A"
                hora_rep = v.get("time") or v.get("hora") or "N/A"

                maps_url = gerar_maps_url(lat, lon)

                bloco = [
                    "---",
                    f"**🚗 {nome}** | Placa: {placa}",
                    f"- Ignição: {ignicao}",
                    f"- Velocidade: {velocidade} km/h",
                    f"- Evento: {evento}",
                    f"- Condutor: {condutor}",
                    f"- Odômetro: {odometro} km",
                    f"- Último reporte: {data_rep} às {hora_rep}",
                    f"- Local: {geo}",
                ]

                if maps_url:
                    bloco.append(f"- 🗺️ Mapa: {maps_url}")

                linhas.extend(bloco)

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # BUSCAR VEÍCULO
    # =====================================================

    @mcp.tool(name="buscar_veiculo")
    async def buscar_veiculo(params: BuscarVeiculoInput) -> str:
        """
        Busca um veículo específico pelo nome ou placa e retorna sua localização atual.
        Use quando o usuário perguntar sobre um veículo específico pelo nome ou placa.
        """

        try:
            veiculos = await executar_post("getdata")

            termo = params.nome_ou_placa.lower()

            encontrados = [
                v for v in veiculos
                if termo in str(get_nome_veiculo(v)).lower()
                or termo in str(get_placa(v)).lower()
                or termo in str(get_id_veiculo(v)).lower()
            ]

            if not encontrados:
                return f"Nenhum veículo encontrado com '{params.nome_ou_placa}'."

            linhas = [
                f"🔍 **{len(encontrados)} veículo(s) encontrado(s):**\n"
            ]

            for v in encontrados:
                nome  = get_nome_veiculo(v)
                placa = get_placa(v)
                lat   = v.get("latitude")
                lon   = v.get("longitude")
                geo   = v.get("geo") or v.get("address") or "Local não informado"
                maps_url = gerar_maps_url(lat, lon)

                data_rep = v.get("date") or v.get("fecha") or "N/A"
                hora_rep = v.get("time") or v.get("hora") or "N/A"

                bloco = [
                    f"**🚗 {nome}** | Placa: {placa}",
                    f"- Ignição: {'🔑 Ligado' if v.get('ignition') else '⭕ Desligado'}",
                    f"- Velocidade: {v.get('speed', 0)} km/h",
                    f"- Último reporte: {data_rep} às {hora_rep}",
                    f"- Local: {geo}",
                ]

                if maps_url:
                    bloco.append(f"- 🗺️ Mapa: {maps_url}")

                bloco.append("")
                linhas.extend(bloco)

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # CONSULTAR ODÔMETRO
    # =====================================================

    @mcp.tool(name="consultar_odometro")
    async def consultar_odometro(params: OdometroInput) -> str:
        """
        Consulta o odômetro de um veículo específico pelo ID.
        """

        try:
            dados = await executar_post(
                "getOdometer",
                {"idasset": params.id_veiculo}
            )

            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            odometro = (
                dados.get("odometer")
                or dados.get("odometro")
                or dados.get("km")
                or "N/A"
            )

            return (
                f"🔢 **Odômetro do veículo {params.id_veiculo}:**\n"
                f"- Total: {odometro} km"
            )

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # HISTÓRICO DE EVENTOS
    # =====================================================

    @mcp.tool(name="historico_eventos")
    async def historico_eventos(
        params: HistoricoEventosInput
    ) -> str:
        """
        Consulta o histórico de eventos (alertas, paradas, ignição) de um veículo em um período.
        Use quando o usuário perguntar sobre eventos, alertas ou histórico de um veículo.
        """

        try:
            eventos = await executar_post(
                "historyGetEvents",
                {
                    "idasset": params.id_veiculo,
                    "date_begin": params.data_inicio,
                    "date_end": params.data_fim,
                }
            )

            if not eventos:
                return (
                    f"Nenhum evento encontrado entre "
                    f"{params.data_inicio} e {params.data_fim}."
                )

            linhas = [
                f"📋 **Histórico de Eventos — {len(eventos)} evento(s)**\n"
            ]

            for e in limitar_lista(eventos, MAX_REGISTROS):
                data  = e.get("date") or e.get("fecha") or "N/A"
                hora  = e.get("time") or e.get("hora") or "N/A"
                event = e.get("event") or e.get("evento") or "N/A"
                vel   = e.get("speed", 0)

                linhas.append(
                    f"- {data} {hora} | {event} | Vel: {vel} km/h"
                )

            if len(eventos) > MAX_REGISTROS:
                linhas.append(
                    f"\n_... e mais {len(eventos) - MAX_REGISTROS} eventos._"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # HISTÓRICO DE POSIÇÕES
    # =====================================================

    @mcp.tool(name="historico_posicoes")
    async def historico_posicoes(
        params: HistoricoPosicaoInput
    ) -> str:
        """
        Consulta o histórico de posições GPS de um veículo em um período de tempo.
        Use quando o usuário perguntar sobre rota percorrida, trajeto ou posições históricas.
        """

        try:
            posicoes = await executar_post(
                "historyGet",
                {
                    "idasset": params.id_veiculo,
                    "date_begin": params.data_inicio,
                    "date_end": params.data_fim,
                }
            )

            if not posicoes:
                return "Nenhuma posição encontrada."

            linhas = [
                f"📍 **Histórico de Posições — {len(posicoes)} registro(s)**\n"
            ]

            for p in limitar_lista(posicoes, MAX_REGISTROS):
                data = p.get("date") or p.get("fecha") or "N/A"
                hora = p.get("time") or p.get("hora") or "N/A"
                vel  = p.get("speed", 0)
                lat  = p.get("latitude", "N/A")
                lon  = p.get("longitude", "N/A")
                geo  = p.get("geo") or p.get("address") or ""

                linha = (
                    f"- {data} {hora} | "
                    f"Vel: {vel} km/h | "
                    f"[{lat}, {lon}]"
                )

                if geo:
                    linha += f" | {geo}"

                linhas.append(linha)

            if len(posicoes) > MAX_REGISTROS:
                linhas.append(
                    f"\n_... e mais {len(posicoes) - MAX_REGISTROS} registros._"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # MARCAS E MODELOS
    # =====================================================

    @mcp.tool(name="listar_marcas_modelos")
    async def listar_marcas_modelos() -> str:
        """
        Lista todas as marcas e modelos de veículos disponíveis na plataforma.
        """

        try:
            dados = await executar_post("getBrandsAndModels")

            if not dados:
                return "Nenhuma marca/modelo encontrado."

            linhas = ["🚘 **Marcas e Modelos Disponíveis:**\n"]

            for marca in limitar_lista(dados, 30):
                # API pode retornar 'name', 'brand' ou 'marca'
                nome = (
                    marca.get("name")
                    or marca.get("brand")
                    or marca.get("marca")
                    or "N/A"
                )

                modelos = marca.get("models") or marca.get("modelos") or []

                nomes_modelos = [
                    m.get("name") or m.get("nombre") or m.get("modelo") or ""
                    for m in modelos[:10]
                    if isinstance(m, dict)
                ]
                nomes_modelos = [n for n in nomes_modelos if n]

                linhas.append(
                    f"**{nome}**: "
                    f"{', '.join(nomes_modelos) if nomes_modelos else 'Sem modelos'}"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)