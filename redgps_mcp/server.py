#!/usr/bin/env python3
# server.py — MCP Server RedGPS

import os
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tools.clientes import registrar_tools_clientes
from tools.veiculos import registrar_tools_veiculos
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.applications import Starlette

# ─── Middleware para corrigir o Host header do ngrok ─────────────────────────
class FixHostMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Substitui o host pelo localhost para o FastMCP aceitar
        request.scope["headers"] = [
            (k, b"localhost:8000") if k == b"host" else (k, v)
            for k, v in request.scope["headers"]
        ]
        return await call_next(request)

# ─── Inicializa o servidor MCP ────────────────────────────────────────────────
mcp = FastMCP(
    name="RedGPS",
    instructions="""
    Você é um assistente especializado em gestão de frotas e rastreamento GPS via RedGPS.

    CLIENTES:
    - listar_clientes: lista todos os clientes da plataforma
    - dados_cliente: retorna dados detalhados da conta atual
    - meu_usuario: retorna informações do usuário autenticado

    VEÍCULOS:
    - listar_veiculos: lista todos os veículos cadastrados
    - localizacao_veiculos: localização em tempo real de toda a frota
    - buscar_veiculo: busca um veículo específico pelo nome ou placa

    Responda sempre em português do Brasil.
    """,
    json_response=True,
)

# ─── Registra as tools ────────────────────────────────────────────────────────
registrar_tools_clientes(mcp)
registrar_tools_veiculos(mcp)

# ─── Inicia o servidor ────────────────────────────────────────────────────────
if __name__ == "__main__":
    load_dotenv()

    apikey = os.getenv("REDGPS_APIKEY", "")
    if not apikey or apikey == "seu_token_aqui":
        print("⚠️  ATENÇÃO: Configure seu REDGPS_APIKEY no arquivo .env!")
    else:
        print(f"✅ Token configurado: {apikey[:8]}...")

    print("🚀 Iniciando RedGPS MCP Server...")
    print("📡 http://0.0.0.0:8000/mcp")
    print("-" * 50)

    # Aplica o middleware no app do FastMCP
    app = mcp.streamable_http_app()
    app.add_middleware(FixHostMiddleware)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )