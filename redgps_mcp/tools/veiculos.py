# =============================================================================
# tools/veiculos.py
# =============================================================================
#
# OBJETIVO:
#   Este arquivo registra todas as "tools" (ferramentas) do MCP Server
#   relacionadas a VEÍCULOS, LOCALIZAÇÃO, HISTÓRICO e ODÔMETRO.
#
# COMO FUNCIONA NA PRÁTICA:
#   Quando o usuário digita "Onde está o veículo ABC1234?" no Claude,
#   o Claude lê as docstrings das tools, identifica que "buscar_veiculo"
#   é a ferramenta certa, extrai "ABC1234" como parâmetro, chama a função,
#   recebe o resultado formatado e apresenta ao usuário.
#
# ESTRUTURA DO ARQUIVO:
#   1. Imports
#   2. Constantes de configuração
#   3. Helpers (funções auxiliares reutilizáveis)
#   4. Validadores Pydantic (modelos de parâmetros das tools)
#   5. Registro das tools via registrar_tools_veiculos(mcp)
#
# ENDPOINTS USADOS (todos POST para https://api.service24gps.com/api/v1/):
#   vehicleGetAll         → lista simples de veículos
#   vehicleGetAllComplete → lista completa com marca, modelo, sensores
#   getdata               → localização em tempo real
#   getOdometer           → odômetro de um veículo
#   historyGetEvents      → histórico de eventos (alertas, ignição, paradas)
#   historyGet            → histórico de posições GPS
#   getBrandsAndModels    → marcas e modelos disponíveis
#
# =============================================================================

from datetime import datetime
from typing import Any, Dict, List

import asyncio

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

from utils.api_client import post, tratar_erro


# =============================================================================
# CONSTANTES DE CONFIGURAÇÃO
# =============================================================================

# Tempo máximo de espera pela API (em segundos).
# Se a API demorar mais, levanta asyncio.TimeoutError (tratado em tratar_erro).
TIMEOUT_API = 15

# Limites de registros nas respostas para evitar mensagens gigantes no chat.
# O Claude tem limite de contexto — respostas muito longas causam corte.
MAX_REGISTROS = 50   # histórico de posições e eventos
MAX_VEICULOS  = 100  # listagem de veículos


# =============================================================================
# HELPERS — FUNÇÕES AUXILIARES REUTILIZÁVEIS
# =============================================================================

async def executar_post(endpoint: str, payload: Dict[str, Any] | None = None):
    """
    Executa uma chamada POST à API RedGPS com timeout e validação de status.

    PARÂMETROS:
      endpoint : nome do endpoint sem URL base (ex: "vehicleGetAll")
      payload  : parâmetros extras além de apikey/token, injetados pelo api_client.

    RETORNA:
      O valor de resultado["data"] — pode ser list ou dict dependendo do endpoint.

    LANÇA:
      Exception com mensagem clara se status != 200
      asyncio.TimeoutError se demorar mais que TIMEOUT_API segundos
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
    Gera uma URL do Google Maps a partir de latitude e longitude.
    Retorna "" se lat/lon forem None, "" ou "N/A".
    """
    if lat in [None, "", "N/A"] or lon in [None, "", "N/A"]:
        return ""
    return f"https://maps.google.com/?q={lat},{lon}"


def status_ativo(veiculo: Dict[str, Any]) -> str:
    """
    Lê o campo 'status' de um veículo e retorna emoji visual.
    A API RedGPS usa inteiro: 1 = ativo, 0 = inativo.
    """
    try:
        status = int(veiculo.get("status", 0))
        return "✅" if status == 1 else "⛔"
    except Exception:
        return "⛔"


def limitar_lista(lista: List[Any], limite: int) -> List[Any]:
    """Retorna os primeiros N itens de uma lista."""
    return lista[:limite]


# ─── Helpers específicos para campos de veículo ──────────────────────────────

def get_nome_veiculo(v: Dict[str, Any]) -> str:
    """
    Retorna o nome/identificação do veículo.
    Tenta campos em espanhol primeiro (vehicleGetAll), depois inglês (getdata) e PascalCase.
    """
    return (
        v.get("nombre")
        or v.get("name")
        or v.get("UnitId")
        or v.get("unitId")
        or v.get("patente")
        or v.get("plate")
        or v.get("UnitPlate")
        or v.get("unitPlate")
        or v.get("device")
        or "N/A"
    )


def get_placa(v: Dict[str, Any]) -> str:
    """Retorna a placa — 'patente' (espanhol), 'plate' (inglês) ou 'UnitPlate' (PascalCase)."""
    return (
        v.get("patente")
        or v.get("plate")
        or v.get("UnitPlate")
        or v.get("unitPlate")
        or "N/A"
    )


def get_marca(v: Dict[str, Any]) -> str:
    """Retorna a marca — 'marca' (espanhol) ou 'brand' (inglês)."""
    return v.get("marca") or v.get("brand") or "N/A"


def get_modelo(v: Dict[str, Any]) -> str:
    """Retorna o modelo — 'modelo' (espanhol) ou 'model' (inglês)."""
    return v.get("modelo") or v.get("model") or "N/A"


def get_ano(v: Dict[str, Any]) -> str:
    """
    Retorna o ano do veículo.
    'anio' é o campo em espanhol (ñ substituído por 'ni' na API).
    Trata '0' como não informado.
    """
    ano = v.get("anio") or v.get("year") or "N/A"
    return "N/A" if str(ano) == "0" else str(ano)


def get_cor(v: Dict[str, Any]) -> str:
    """Retorna a cor — campo 'color' é igual em espanhol e inglês."""
    return v.get("color") or "N/A"


def get_id_veiculo(v: Dict[str, Any]) -> str:
    """
    Retorna o ID único do veículo/ativo.
    A API usa 'id', 'idasset' ou 'asset' dependendo do endpoint e versão.

    CORREÇÃO: o original usava `str(v.get("id") or "")`, que converte o
    inteiro 0 para "" porque 0 é falsy em Python. Agora verificamos
    explicitamente se o valor é None antes de descartar.
    """
    for chave in ("id", "idasset", "asset"):
        valor = v.get(chave)
        if valor is not None and str(valor).strip() != "":
            return str(valor)
    return "N/A"


def get_condutor(v: Dict[str, Any]) -> str:
    """
    Retorna o nome do condutor identificado no momento.
    Suporta campos em espanhol, inglês e PascalCase.
    """
    return (
        v.get("conductor")
        or v.get("Conductor")
        or v.get("driver")
        or v.get("Driver")
        or "Não identificado"
    )


def get_grupo(v: Dict[str, Any]) -> str:
    """Retorna o grupo ao qual o veículo pertence."""
    return v.get("grupo") or v.get("group") or "N/A"


def escolher_valor(v: Dict[str, Any], *chaves, default=None):
    """
    Retorna o primeiro valor não-None e não-vazio encontrado nas chaves fornecidas.

    CORREÇÃO: o original retornava `default` apenas quando o valor era None
    ou "". Agora também descarta o inteiro 0 nos callers que usam `or` chain?
    Não — aqui mantemos 0 como valor válido. Os callers que precisam de
    string de exibição devem converter com str() após chamar esta função.
    """
    for chave in chaves:
        if chave in v:
            valor = v[chave]
            if valor is not None and valor != "":
                return valor
    return default


def valor_verdadeiro(v: Dict[str, Any], *chaves) -> bool:
    """
    Interpreta valores verdadeiros comuns para campos booleanos.
    Suporta 1, '1', True, 'true', 'True', 'on', 'yes', 'sim'.
    """
    valor = escolher_valor(v, *chaves)
    if valor is None:
        return False
    return str(valor).strip().lower() in {"1", "true", "yes", "sim", "on"}


def get_tipo(v: Dict[str, Any]) -> str:
    """Retorna o tipo do veículo (carro, moto, caminhão, etc.)."""
    return escolher_valor(v, "tipo_vehiculo", "type", "Type", "Tipo", "tipo") or "N/A"


# =============================================================================
# VALIDADORES PYDANTIC — MODELOS DE PARÂMETROS DAS TOOLS
# =============================================================================

class BuscarVeiculoInput(BaseModel):
    """Parâmetros para buscar_veiculo."""

    nome_ou_placa: str = Field(
        ...,
        description=(
            "Nome do veículo, placa (ex: 'ABC1234' ou 'ABC-1234') "
            "ou qualquer identificador usado no sistema. "
            "A busca é parcial e não diferencia maiúsculas/minúsculas."
        )
    )

    @field_validator("nome_ou_placa")
    @classmethod
    def validar_nome(cls, value):
        """Remove espaços extras e rejeita strings vazias."""
        value = value.strip()
        if not value:
            raise ValueError("Informe um nome ou placa válida.")
        return value


class OdometroInput(BaseModel):
    """Parâmetros para consultar_odometro."""

    id_veiculo: str = Field(
        ...,
        description=(
            "ID numérico do veículo/ativo no RedGPS. "
            "Obtenha este ID via listar_veiculos (coluna 'ID') "
            "antes de chamar esta tool."
        )
    )


class HistoricoEventosInput(BaseModel):
    """Parâmetros para historico_eventos."""

    id_veiculo: str = Field(
        ...,
        description=(
            "ID numérico do veículo. "
            "Use listar_veiculos para descobrir o ID se necessário."
        )
    )

    data_inicio: str = Field(
        ...,
        description=(
            "Data de início do período no formato YYYY-MM-DD. "
            "Exemplo: '2026-01-01' para 1º de janeiro de 2026."
        )
    )

    data_fim: str = Field(
        ...,
        description=(
            "Data de fim do período no formato YYYY-MM-DD. "
            "Deve ser igual ou posterior a data_inicio. "
            "Exemplo: '2026-01-31' para 31 de janeiro de 2026."
        )
    )

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def validar_data(cls, value):
        """Garante que a data esteja no formato correto (YYYY-MM-DD)."""
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Data inválida: '{value}'. Use o formato YYYY-MM-DD (ex: '2026-01-15')."
            )
        return value


class HistoricoPosicaoInput(BaseModel):
    """Parâmetros para historico_posicoes."""

    id_veiculo: str = Field(
        ...,
        description="ID numérico do veículo. Use listar_veiculos para descobrir o ID."
    )

    data_inicio: str = Field(
        ...,
        description=(
            "Data e hora de início no formato YYYY-MM-DD HH:MM:SS. "
            "Exemplo: '2026-01-15 08:00:00' para 15/01/2026 às 08h."
        )
    )

    data_fim: str = Field(
        ...,
        description=(
            "Data e hora de fim no formato YYYY-MM-DD HH:MM:SS. "
            "Exemplo: '2026-01-15 18:00:00' para 15/01/2026 às 18h."
        )
    )

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def validar_data_hora(cls, value):
        """Valida formato YYYY-MM-DD HH:MM:SS."""
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(
                f"Data/hora inválida: '{value}'. "
                "Use o formato YYYY-MM-DD HH:MM:SS (ex: '2026-01-15 08:00:00')."
            )
        return value


# =============================================================================
# REGISTRO DAS TOOLS MCP
# =============================================================================

def registrar_tools_veiculos(mcp: FastMCP):
    """
    Registra todas as tools de veículos no servidor MCP.
    Chamada uma vez em server.py durante a inicialização do servidor.
    """

    @mcp.tool(name="debug_dados_brutos")
    async def debug_dados_brutos() -> str:
        """
        Retorna os dados brutos do primeiro veículo da API para diagnóstico.
        Use quando precisar ver os campos exatos que a API está retornando.
        """
        import json

        resultados = {}
        for endpoint in ["vehicleGetAll", "getdata", "vehicleGetAllComplete"]:
            try:
                r = await asyncio.wait_for(post(endpoint, None), timeout=TIMEOUT_API)
                dados = r.get("data", [])
                primeiro = dados[0] if isinstance(dados, list) and dados else dados
                resultados[endpoint] = {
                    "status": r.get("status"),
                    "campos": list(primeiro.keys()) if isinstance(primeiro, dict) else str(primeiro)[:200],
                    "amostra": {k: v for k, v in list(primeiro.items())[:10]} if isinstance(primeiro, dict) else primeiro,
                }
            except Exception as e:
                resultados[endpoint] = {"erro": str(e)}

        return f"```json\n{json.dumps(resultados, indent=2, ensure_ascii=False)}\n```"


    # =========================================================================
    # TOOL: listar_veiculos
    # =========================================================================
    @mcp.tool(name="listar_veiculos")
    async def listar_veiculos() -> str:
        """
        Lista todos os veículos/ativos cadastrados e atribuídos ao usuário autenticado.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quantos veículos existem na frota
        - Quais veículos estão cadastrados
        - IDs dos veículos (necessários para histórico e odômetro)
        - Status (ativo/inativo) de cada veículo
        - Grupos ou tipos de veículos

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Liste os veículos da frota"
        - "Quantos veículos tenho cadastrados?"
        - "Quais são os IDs dos veículos?"
        - "Me mostra a lista de ativos"

        DIFERENÇA PARA listar_veiculos_completo:
        - listar_veiculos → tabela resumida, mais rápida
        - listar_veiculos_completo → bloco detalhado com marca, modelo, sensores

        NOTA TÉCNICA:
        - Retorna máximo de 100 veículos por chamada
        - IDs desta lista são usados em consultar_odometro e historico_eventos
        """
        try:
            veiculos = await executar_post("vehicleGetAll")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [
                f"🚗 **Total de veículos: {len(veiculos)}**\n",
                "| # | Nome | Placa | ID | Tipo | Grupo | Ativo |",
                "|---|------|-------|----|------|-------|-------|",
            ]

            for i, v in enumerate(limitar_lista(veiculos, MAX_VEICULOS), start=1):
                nome  = get_nome_veiculo(v)
                placa = get_placa(v)
                id_v  = get_id_veiculo(v)
                tipo  = get_tipo(v)
                grupo = get_grupo(v)
                ativo = status_ativo(v)
                linhas.append(f"| {i} | {nome} | {placa} | {id_v} | {tipo} | {grupo} | {ativo} |")

            if len(veiculos) > MAX_VEICULOS:
                linhas.append(f"\n_Exibindo {MAX_VEICULOS} de {len(veiculos)} veículos._")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_veiculos_completo
    # =========================================================================
    @mcp.tool(name="listar_veiculos_completo")
    async def listar_veiculos_completo() -> str:
        """
        Lista todos os veículos com informações técnicas completas.
        Inclui marca, modelo, ano, cor, placa, condutor, grupo, tipo e sensores instalados.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Especificações técnicas dos veículos (marca, modelo, ano)
        - Quais sensores estão instalados em cada veículo
        - Cor ou características físicas dos veículos
        - Condutor atribuído a cada veículo no cadastro

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Me dá os detalhes completos dos veículos"
        - "Qual a marca e modelo dos carros da frota?"
        - "Quais sensores tem o veículo X?"
        - "Qual o ano dos veículos?"

        DIFERENÇA PARA listar_veiculos:
        - listar_veiculos → tabela resumida, ideal para visão geral
        - listar_veiculos_completo → detalhes por veículo, mais pesado

        NOTA TÉCNICA:
        - vehicleGetAllComplete retorna o mesmo conjunto de vehicleGetAll
          mais campos extras: marca, modelo, anio, color, sensores
        """
        try:
            veiculos = await executar_post("vehicleGetAllComplete")

            if not veiculos:
                return "Nenhum veículo encontrado."

            linhas = [f"🚗 **Veículos — Informações Completas ({len(veiculos)} total)**\n"]

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
                    f"- Marca: {marca}  |  Modelo: {modelo}  |  Ano: {ano}  |  Cor: {cor}",
                    f"- Tipo: {tipo}  |  Grupo: {grupo}",
                    f"- Condutor cadastrado: {condutor}",
                    f"- Status: {ativo}",
                ]

                sensores = v.get("sensors") or v.get("sensores")
                if sensores and isinstance(sensores, dict):
                    nomes_sensores = [
                        s.get("name") or k
                        for k, s in sensores.items()
                        if isinstance(s, dict)
                    ]
                    nomes_sensores = [n for n in nomes_sensores if n]
                    if nomes_sensores:
                        bloco.append(f"- Sensores: {', '.join(nomes_sensores[:5])}")

                linhas.extend(bloco)

            if len(veiculos) > MAX_VEICULOS:
                linhas.append(f"\n_Exibindo {MAX_VEICULOS} de {len(veiculos)} veículos._")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: localizacao_veiculos
    # =========================================================================
    @mcp.tool(name="localizacao_veiculos")
    async def localizacao_veiculos() -> str:
        """
        Retorna a localização e status em tempo real de TODOS os veículos da frota.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Onde estão os veículos agora (localização atual)
        - Quais veículos estão com ignição ligada ou desligada
        - Velocidade atual dos veículos
        - Quem está dirigindo cada veículo agora (condutor identificado)
        - Odômetro atual e quilometragem
        - Último reporte de cada rastreador
        - Qual evento o veículo está executando

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Onde estão os veículos agora?"
        - "Quantos veículos estão com ignição ligada?"
        - "Qual a velocidade atual dos carros?"
        - "Me mostra a frota em tempo real"
        - "Quem está dirigindo agora?"

        PARA UM VEÍCULO ESPECÍFICO:
        Use buscar_veiculo com o nome ou placa — mais rápido e direto.

        NOTA TÉCNICA:
        - getdata é o endpoint mais chamado da API RedGPS
        - Retorna snapshot do momento atual de todos os rastreadores
        - Campos principais: latitude, longitude, speed, ignition, event,
          conductor/driver, odometer, date, time, geo/address
        """
        try:
            veiculos = await executar_post("getdata")

            if not veiculos:
                return "Nenhum dado de localização encontrado."

            linhas = [f"📡 **Localização em Tempo Real — {len(veiculos)} veículo(s)**\n"]

            for v in limitar_lista(veiculos, MAX_VEICULOS):
                nome  = get_nome_veiculo(v)
                placa = get_placa(v)

                lat = escolher_valor(v, "latitude", "Latitude")
                lon = escolher_valor(v, "longitude", "Longitude")

                velocidade = escolher_valor(
                    v, "speed", "Speed", "GpsSpeed", "gpsSpeed", default=0
                )
                ignicao = "🔑 Ligado" if valor_verdadeiro(v, "ignition", "Ignition") else "⭕ Desligado"
                condutor = get_condutor(v)
                geo = (
                    escolher_valor(v, "geo", "Geo", "address", "Address", "endereco", "Domicilio")
                    or "Local não informado"
                )
                odometro = escolher_valor(
                    v, "odometer", "Odometer", "odometro", "km", "Km", default="N/A"
                )
                evento = escolher_valor(
                    v, "event", "Event", "evento", "Evento", default="N/A"
                )
                data_rep = escolher_valor(
                    v, "date", "Date", "fecha", "ReportDate", "InsertionDate", default="N/A"
                )
                hora_rep = escolher_valor(v, "time", "Time", "hora", default="N/A")
                maps_url = gerar_maps_url(lat, lon)

                bloco = [
                    "---",
                    f"**🚗 {nome}** | Placa: {placa}",
                    f"- Ignição: {ignicao}  |  Velocidade: {velocidade} km/h",
                    f"- Evento: {evento}",
                    f"- Condutor: {condutor}",
                    f"- Odômetro: {odometro} km",
                    f"- Último reporte: {data_rep} às {hora_rep}",
                    f"- Local: {geo}",
                ]

                if maps_url:
                    bloco.append(f"- 🗺️ Mapa: {maps_url}")

                linhas.extend(bloco)

            if len(veiculos) > MAX_VEICULOS:
                linhas.append(f"\n_Exibindo {MAX_VEICULOS} de {len(veiculos)} veículos._")

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: buscar_veiculo
    # =========================================================================
    @mcp.tool(name="buscar_veiculo")
    async def buscar_veiculo(params: BuscarVeiculoInput) -> str:
        """
        Busca um ou mais veículos específicos pelo nome ou placa e retorna localização atual.

        USE ESTA TOOL quando o usuário perguntar sobre um veículo específico:
        - Onde está determinado veículo (por nome ou placa)
        - Status de ignição de um veículo específico
        - Velocidade atual de um veículo específico

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Onde está o veículo ABC1234?"
        - "Qual a localização do Fiat Uno?"
        - "O caminhão 007 está ligado?"
        - "Me mostra a posição do veículo de placa XYZ-9876"

        NOTA TÉCNICA:
        - A busca é feita localmente: buscamos TODOS os veículos via getdata
          e filtramos pelo termo informado. A API RedGPS não suporta filtro
          por nome/placa diretamente no endpoint getdata.
        - A busca é parcial e não diferencia maiúsculas/minúsculas.
        """
        try:
            veiculos = await executar_post("getdata")

            termo = params.nome_ou_placa.lower().strip()

            encontrados = [
                v for v in veiculos
                if termo in str(get_nome_veiculo(v)).lower()
                or termo in str(get_placa(v)).lower()
                or termo in str(get_id_veiculo(v)).lower()
            ]

            if not encontrados:
                return (
                    f"Nenhum veículo encontrado com '{params.nome_ou_placa}'.\n"
                    f"Dica: use listar_veiculos para ver todos os nomes e placas disponíveis."
                )

            linhas = [f"🔍 **{len(encontrados)} veículo(s) encontrado(s):**\n"]

            for v in encontrados:
                nome     = get_nome_veiculo(v)
                placa    = get_placa(v)
                lat      = escolher_valor(v, "latitude", "Latitude")
                lon      = escolher_valor(v, "longitude", "Longitude")
                geo      = (
                    escolher_valor(v, "geo", "Geo", "address", "Address", "endereco", "Domicilio")
                    or "Local não informado"
                )
                data_rep = escolher_valor(
                    v, "date", "Date", "fecha", "ReportDate", "InsertionDate", default="N/A"
                )
                hora_rep = escolher_valor(v, "time", "Time", "hora", default="N/A")
                maps_url = gerar_maps_url(lat, lon)

                bloco = [
                    f"**🚗 {nome}** | Placa: {placa}",
                    f"- Ignição: {'🔑 Ligado' if valor_verdadeiro(v, 'ignition', 'Ignition') else '⭕ Desligado'}",
                    f"- Velocidade: {escolher_valor(v, 'speed', 'Speed', 'GpsSpeed', 'gpsSpeed', default=0)} km/h",
                    f"- Condutor: {get_condutor(v)}",
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


    # =========================================================================
    # TOOL: consultar_odometro
    # =========================================================================
    @mcp.tool(name="consultar_odometro")
    async def consultar_odometro(params: OdometroInput) -> str:
        """
        Consulta o odômetro acumulado de um veículo específico pelo ID.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quilometragem total de um veículo
        - Quantos km um veículo já rodou
        - Odômetro de um ativo específico

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Qual o odômetro do veículo ID 42?"
        - "Quantos km o ativo 15 já rodou?"
        - "Me dá a quilometragem total do veículo 7"

        FLUXO RECOMENDADO:
        Se o usuário não souber o ID, use listar_veiculos primeiro para
        obter o ID (coluna "ID" da tabela), depois chame consultar_odometro.

        NOTA TÉCNICA:
        - O odômetro retornado é o valor acumulado registrado no sistema.
        - Pode diferir do odômetro físico do veículo se houver ajuste manual.
        - Endpoint: POST /getOdometer com parâmetro: idasset = ID do veículo
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
                f"🔢 **Odômetro — Veículo ID {params.id_veiculo}:**\n"
                f"- Quilometragem total: **{odometro} km**"
            )

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: historico_eventos
    # =========================================================================
    @mcp.tool(name="historico_eventos")
    async def historico_eventos(params: HistoricoEventosInput) -> str:
        """
        Consulta o histórico de eventos de um veículo em um período de datas.

        Eventos incluem: ignição ligada/desligada, excesso de velocidade,
        paradas, saída/entrada de cerca geográfica, alertas de manutenção, etc.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - O que aconteceu com um veículo em determinado período
        - Quantas vezes o veículo ligou/desligou
        - Alertas gerados por um veículo
        - Histórico de eventos ou ocorrências

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Quais eventos o veículo 42 teve hoje?"
        - "Me mostra o histórico do ativo 15 de 01/01 a 31/01"
        - "Quantas vezes o veículo 7 excedeu a velocidade na semana?"
        - "Quais alertas foram gerados pelo veículo 3?"

        FLUXO RECOMENDADO:
        1. Use listar_veiculos para obter o ID do veículo
        2. Chame historico_eventos com o ID e o período desejado

        NOTA TÉCNICA:
        - Exibe no máximo 50 eventos por consulta (MAX_REGISTROS)
        - Para períodos longos com muitos eventos, considere reduzir o intervalo
        - Endpoint: POST /historyGetEvents
          Parâmetros: idasset, date_begin (YYYY-MM-DD), date_end (YYYY-MM-DD)
        """
        try:
            eventos = await executar_post(
                "historyGetEvents",
                {
                    "idasset":    params.id_veiculo,
                    "date_begin": params.data_inicio,
                    "date_end":   params.data_fim,
                }
            )

            if not eventos:
                return (
                    f"Nenhum evento encontrado para o veículo {params.id_veiculo} "
                    f"entre {params.data_inicio} e {params.data_fim}."
                )

            # CORREÇÃO: f-strings separadas por vírgula para serem itens distintos
            # da lista. Sem a vírgula, Python concatena as f-strings em tempo de
            # compilação, transformando as 3 linhas em uma única string — o que
            # faz o cabeçalho aparecer colado em uma linha só no chat.
            linhas = [
                f"📋 **Histórico de Eventos — Veículo {params.id_veiculo}**\n",
                f"📅 Período: {params.data_inicio} a {params.data_fim}\n",
                f"📊 Total: {len(eventos)} evento(s)\n",
            ]

            for e in limitar_lista(eventos, MAX_REGISTROS):
                data  = e.get("date")  or e.get("fecha") or "N/A"
                hora  = e.get("time")  or e.get("hora")  or "N/A"
                event = e.get("event") or e.get("evento") or "N/A"
                vel   = e.get("speed", 0)
                lat   = e.get("latitude", "")
                lon   = e.get("longitude", "")
                maps  = gerar_maps_url(lat, lon)

                linha = f"- {data} {hora} | **{event}** | Vel: {vel} km/h"
                if maps:
                    linha += f" | [📍 Mapa]({maps})"
                linhas.append(linha)

            if len(eventos) > MAX_REGISTROS:
                linhas.append(
                    f"\n_Exibindo {MAX_REGISTROS} de {len(eventos)} eventos. "
                    f"Reduza o período para ver mais detalhes._"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: historico_posicoes
    # =========================================================================
    @mcp.tool(name="historico_posicoes")
    async def historico_posicoes(params: HistoricoPosicaoInput) -> str:
        """
        Consulta o histórico completo de posições GPS de um veículo em um período.

        Retorna cada ponto GPS registrado com: data, hora, velocidade,
        coordenadas (latitude/longitude) e endereço.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - A rota percorrida por um veículo
        - O trajeto de um veículo em determinado dia/horário
        - Posições GPS históricas de um ativo
        - Onde o veículo esteve em determinado horário

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Qual foi a rota do veículo 42 hoje de manhã?"
        - "Me mostra o trajeto do ativo 15 de 08h às 18h"
        - "Onde estava o veículo 7 às 14h30 do dia 15/01?"
        - "Histórico de posições do carro 3 nessa semana"

        DIFERENÇA PARA historico_eventos:
        - historico_posicoes → TODAS as posições GPS (pontos de rastreamento)
        - historico_eventos  → apenas EVENTOS significativos (alertas, ignição)

        NOTA TÉCNICA:
        - IMPORTANTE: data_inicio e data_fim precisam incluir HORÁRIO
          (formato YYYY-MM-DD HH:MM:SS), diferente de historico_eventos
          que aceita só a data
        - Exibe no máximo 50 posições (MAX_REGISTROS)
        - Para um dia completo use: data_inicio="2026-01-15 00:00:00"
          e data_fim="2026-01-15 23:59:59"
        - Endpoint: POST /historyGet
          Parâmetros: idasset, date_begin, date_end (YYYY-MM-DD HH:MM:SS)
        """
        try:
            posicoes = await executar_post(
                "historyGet",
                {
                    "idasset":    params.id_veiculo,
                    "date_begin": params.data_inicio,
                    "date_end":   params.data_fim,
                }
            )

            if not posicoes:
                return (
                    f"Nenhuma posição encontrada para o veículo {params.id_veiculo} "
                    f"entre {params.data_inicio} e {params.data_fim}."
                )

            # CORREÇÃO: vírgulas separando cada f-string em item distinto da lista
            linhas = [
                f"📍 **Histórico de Posições — Veículo {params.id_veiculo}**\n",
                f"📅 Período: {params.data_inicio} → {params.data_fim}\n",
                f"📊 Total: {len(posicoes)} registro(s)\n",
            ]

            for p in limitar_lista(posicoes, MAX_REGISTROS):
                data = p.get("date") or p.get("fecha") or "N/A"
                hora = p.get("time") or p.get("hora")  or "N/A"
                vel  = p.get("speed", 0)
                lat  = p.get("latitude",  "N/A")
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
                    f"\n_Exibindo {MAX_REGISTROS} de {len(posicoes)} registros. "
                    f"Reduza o período de consulta para mais detalhes._"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)


    # =========================================================================
    # TOOL: listar_marcas_modelos
    # =========================================================================
    @mcp.tool(name="listar_marcas_modelos")
    async def listar_marcas_modelos() -> str:
        """
        Lista todas as marcas e modelos de veículos disponíveis para cadastro na plataforma.

        USE ESTA TOOL quando o usuário perguntar sobre:
        - Quais marcas de veículos estão disponíveis no sistema
        - Que modelos podem ser cadastrados para determinada marca
        - Opções de veículos para cadastrar um novo ativo

        EXEMPLOS DE PERGUNTAS DO USUÁRIO:
        - "Quais marcas de veículos estão disponíveis?"
        - "Que modelos da Toyota posso cadastrar?"
        - "Me lista as marcas e modelos"

        NOTA TÉCNICA:
        - Exibe no máximo 30 marcas e 10 modelos por marca para não sobrecarregar
        - Endpoint: POST /getBrandsAndModels, sem parâmetros extras
        """
        try:
            dados = await executar_post("getBrandsAndModels")

            if not dados:
                return "Nenhuma marca/modelo encontrado."

            linhas = ["🚘 **Marcas e Modelos Disponíveis:**\n"]

            for marca in limitar_lista(dados, 30):
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
                    f"{', '.join(nomes_modelos) if nomes_modelos else 'Sem modelos cadastrados'}"
                )

            return "\n".join(linhas)

        except Exception as e:
            return tratar_erro(e)