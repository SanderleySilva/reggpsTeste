# utils/api_client.py
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("REDGPS_BASE_URL", "https://api.service24gps.com/api/v1")
APIKEY   = os.getenv("REDGPS_APIKEY", "")
USERNAME = os.getenv("REDGPS_USERNAME", "")
PASSWORD = os.getenv("REDGPS_PASSWORD", "")

# ─── Controle do token em memória ────────────────────────────────────────────
_token: str = ""
_token_obtido_em: float = 0
_TOKEN_DURACAO = 5.5 * 60 * 60  # 5h30 (margem de segurança antes das 6h)


def _token_expirado() -> bool:
    """Verifica se o token está expirado ou ainda não foi obtido."""
    return not _token or (time.time() - _token_obtido_em) > _TOKEN_DURACAO


async def _renovar_token():
    """Chama gettoken e atualiza o token em memória."""
    global _token, _token_obtido_em

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{BASE_URL}/gettoken",
            data={
                "apikey":   APIKEY,
                "token":    "",
                "username": USERNAME,
                "password": PASSWORD,
            }
        )
        response.raise_for_status()
        resultado = response.json()

    if resultado.get("status") != 200:
        raise Exception(f"Falha ao obter token: {resultado}")

    _token = resultado["data"]
    _token_obtido_em = time.time()
    print(f"🔑 Token renovado com sucesso.")


async def post(endpoint: str, extra_data: dict = None) -> dict:
    """
    Faz um POST para a API RedGPS.
    Renova o token automaticamente se estiver expirado.
    """
    global _token

    # Renova o token se necessário
    if _token_expirado():
        await _renovar_token()

    payload = {"apikey": APIKEY, "token": _token}
    if extra_data:
        payload.update(extra_data)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{BASE_URL}/{endpoint.lstrip('/')}",
            data=payload
        )
        response.raise_for_status()
        return response.json()


def tratar_erro(e: Exception) -> str:
    """Traduz erros HTTP para mensagens amigáveis."""
    if isinstance(e, httpx.HTTPStatusError):
        codigo = e.response.status_code
        if codigo == 401:
            return "❌ Erro 401: Credenciais inválidas. Verifique APIKEY, USERNAME e PASSWORD no .env"
        elif codigo == 404:
            return "❌ Erro 404: Endpoint não encontrado."
        elif codigo == 429:
            return "❌ Erro 429: Limite de requisições atingido. Aguarde e tente novamente."
        elif codigo == 500:
            return "❌ Erro 500: Erro interno na API RedGPS."
        return f"❌ Erro HTTP {codigo}: {e.response.text}"
    elif isinstance(e, httpx.TimeoutException):
        return "❌ Timeout: A API RedGPS demorou demais. Tente novamente."
    elif isinstance(e, httpx.ConnectError):
        return "❌ Sem conexão: Verifique sua internet."
    return f"❌ Erro inesperado: {type(e).__name__}: {str(e)}"