#!/usr/bin/env python3
import os
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from tools.clientes import registrar_tools_clientes
from tools.veiculos import registrar_tools_veiculos

load_dotenv()


class FixHostMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.scope["headers"] = [
            (k, b"localhost:8000") if k == b"host" else (k, v)
            for k, v in request.scope["headers"]
        ]
        return await call_next(request)


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
    # CORREÇÃO: removido json_response=True — causa conflito com SSE transport.
    # O FastMCP gerencia a serialização internamente no modo SSE.
)

registrar_tools_clientes(mcp)
registrar_tools_veiculos(mcp)

# CORREÇÃO: trocado streamable_http_app() por sse_app().
#
# O Claude.ai conecta via SSE (Server-Sent Events) no endpoint /sse,
# não via Streamable HTTP. Com streamable_http_app() o handshake de
# inicialização falha silenciosamente e o Claude.ai tenta OAuth como
# fallback — causando o erro "Couldn't register with redegps's sign-in service".
#
# sse_app() expõe:
#   GET  /sse   → stream de eventos (Claude.ai conecta aqui)
#   POST /messages → recebe chamadas de tools
app = mcp.sse_app()

# CORREÇÃO: adicionado CORSMiddleware antes do FixHostMiddleware.
#
# Sem CORS, o browser bloqueia as requisições do Claude.ai para o servidor
# com erro "Access-Control-Allow-Origin missing".
# allow_origins=["*"] libera qualquer origem — adequado para servidor MCP próprio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(FixHostMiddleware)


if __name__ == "__main__":
    apikey = os.getenv("REDGPS_APIKEY", "")
    if not apikey or apikey == "seu_token_aqui":
        print("⚠️  ATENÇÃO: Configure seu REDGPS_APIKEY no arquivo .env!")
    else:
        print(f"✅ Token configurado: {apikey[:8]}...")

    print("🚀 Iniciando RedGPS MCP Server...")
    print("📡 Endpoint SSE: /sse")
    print("📨 Endpoint mensagens: /messages")

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )