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
        Lista todos os veículos cadastrados.
        """

        try:
            veiculos = await executar_post("vehicleGetAll")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [
                f"🚗 **Total de veículos: {len(veiculos)}**\n",
                "| # | Nome/Placa | ID | Ativo |",
                "|---|---|---|---|"
            ]

            for i, v in enumerate(
                limitar_lista(veiculos, MAX_VEICULOS),
                start=1
            ):

                nome = (
                    v.get("name")
                    or v.get("plate")
                    or "N/A"
                )

                id_v = (
                    v.get("id")
                    or v.get("idasset")
                    or "N/A"
                )

                ativo = status_ativo(v)

                linhas.append(
                    f"| {i} | {nome} | {id_v} | {ativo} |"
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
        Lista veículos com detalhes completos.
        """

        try:
            veiculos = await executar_post("vehicleGetAllComplete")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [
                f"🚗 **Veículos — Informações Completas ({len(veiculos)} total)**\n"
            ]

            for v in limitar_lista(veiculos, MAX_VEICULOS):

                nome = v.get("name") or "N/A"

                linhas.append(
                    "\n".join([
                        "---",
                        f"**{nome}**",
                        f"- Placa: {v.get('plate', 'N/A')}",
                        f"- Marca: {v.get('brand', 'N/A')}",
                        f"- Modelo: {v.get('model', 'N/A')}",
                        f"- Ano: {v.get('year', 'N/A')}",
                        f"- Cor: {v.get('color', 'N/A')}",
                    ])
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # LOCALIZAÇÃO DOS VEÍCULOS
    # =====================================================

    @mcp.tool(name="localizacao_veiculos")
    async def localizacao_veiculos() -> str:
        """
        Retorna localização em tempo real.
        """

        try:
            veiculos = await executar_post("getdata")

            if not veiculos:
                return "Nenhum dado de localização encontrado."

            linhas = [
                f"📡 **Localização em Tempo Real — {len(veiculos)} veículo(s)**\n"
            ]

            for v in limitar_lista(veiculos, MAX_VEICULOS):

                nome = v.get("name") or v.get("device") or "N/A"

                lat = v.get("latitude")
                lon = v.get("longitude")

                velocidade = v.get("speed", 0)

                ignicao = "🔑 Ligado" if v.get("ignition") else "⭕ Desligado"

                geo = v.get("geo") or v.get("address") or "Local não informado"

                maps_url = gerar_maps_url(lat, lon)

                linhas.extend([
                    "---",
                    f"**🚗 {nome}**",
                    f"- Ignição: {ignicao}",
                    f"- Velocidade: {velocidade} km/h",
                    f"- Evento: {v.get('event', 'N/A')}",
                    f"- Condutor: {v.get('driver', 'Não identificado')}",
                    f"- Odômetro: {v.get('odometer', 'N/A')} km",
                    f"- Último reporte: {v.get('date', 'N/A')} às {v.get('time', 'N/A')}",
                    f"- Local: {geo}",
                ])

                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # BUSCAR VEÍCULO
    # =====================================================

    @mcp.tool(name="buscar_veiculo")
    async def buscar_veiculo(params: BuscarVeiculoInput) -> str:
        """
        Busca veículo por nome ou placa.
        """

        try:
            veiculos = await executar_post("getdata")

            termo = params.nome_ou_placa.lower()

            encontrados = [
                v for v in veiculos
                if termo in str(v.get("name", "")).lower()
                or termo in str(v.get("plate", "")).lower()
            ]

            if not encontrados:
                return f"Nenhum veículo encontrado com '{params.nome_ou_placa}'."

            linhas = [
                f"🔍 **{len(encontrados)} veículo(s) encontrado(s):**\n"
            ]

            for v in encontrados:

                nome = v.get("name") or v.get("device") or "N/A"

                lat = v.get("latitude")
                lon = v.get("longitude")

                maps_url = gerar_maps_url(lat, lon)

                linhas.extend([
                    f"**🚗 {nome}**",
                    f"- Ignição: {'🔑 Ligado' if v.get('ignition') else '⭕ Desligado'}",
                    f"- Velocidade: {v.get('speed', 0)} km/h",
                    f"- Último reporte: {v.get('date', 'N/A')} às {v.get('time', 'N/A')}",
                ])

                geo = v.get("geo") or v.get("address")

                if geo:
                    linhas.append(f"- Local: {geo}")

                if maps_url:
                    linhas.append(f"- Mapa: {maps_url}")

                linhas.append("")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)

    # =====================================================
    # CONSULTAR ODÔMETRO
    # =====================================================

    @mcp.tool(name="consultar_odometro")
    async def consultar_odometro(params: OdometroInput) -> str:
        """
        Consulta odômetro do veículo.
        """

        try:
            dados = await executar_post(
                "getOdometer",
                {"idasset": params.id_veiculo}
            )

            if isinstance(dados, list):
                dados = dados[0] if dados else {}

            return (
                f"🔢 **Odômetro do veículo {params.id_veiculo}:**\n"
                f"- Total: {dados.get('odometer', 'N/A')} km"
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
        Consulta histórico de eventos.
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

                linhas.append(
                    f"- {e.get('date')} {e.get('time')} | "
                    f"{e.get('event', 'N/A')} | "
                    f"Vel: {e.get('speed', 0)} km/h"
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
        Consulta histórico de posições GPS.
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

                linhas.append(
                    f"- {p.get('date')} {p.get('time')} | "
                    f"Vel: {p.get('speed', 0)} km/h | "
                    f"[{p.get('latitude', 'N/A')}, {p.get('longitude', 'N/A')}]"
                )

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
        Lista marcas e modelos disponíveis.
        """

        try:
            dados = await executar_post("getBrandsAndModels")

            if not dados:
                return "Nenhuma marca/modelo encontrado."

            linhas = ["🚘 **Marcas e Modelos Disponíveis:**\n"]

            for marca in limitar_lista(dados, 30):

                nome = marca.get("name") or marca.get("brand") or "N/A"

                modelos = marca.get("models") or []

                nomes_modelos = [
                    m.get("name", "")
                    for m in modelos[:10]
                    if m.get("name")
                ]

                linhas.append(
                    f"**{nome}**: "
                    f"{', '.join(nomes_modelos) if nomes_modelos else 'Sem modelos'}"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)