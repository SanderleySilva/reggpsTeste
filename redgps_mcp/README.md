# 🚀 RedGPS MCP Server

Integração do Claude com a API RedGPS via Model Context Protocol (MCP).
Com isso você consulta dados da sua frota e clientes em linguagem natural direto no claude.ai.

---

## 📁 Estrutura do Projeto

```
redgps_mcp/
├── server.py              ← Arquivo principal (execute este)
├── .env                   ← Suas credenciais (não compartilhe!)
├── requirements.txt       ← Dependências Python
├── tools/
│   ├── clientes.py        ← Tools de clientes e usuários
│   └── veiculos.py        ← Tools de veículos e localização
└── utils/
    └── api_client.py      ← Cliente HTTP base para a API RedGPS
```

---

## ⚙️ Configuração (passo a passo)

### 1. Configure suas credenciais

Abra o arquivo `.env` e substitua o token:

```env
REDGPS_APIKEY=seu_token_real_aqui
REDGPS_BASE_URL=https://api.service24gps.com/api/v1
```

### 2. Instale as dependências

No terminal do PyCharm:

```bash
pip install -r requirements.txt
```

### 3. Execute o servidor

```bash
python server.py
```

Você verá:
```
✅ Token configurado: 0af02884...
🚀 Iniciando RedGPS MCP Server...
📡 Modo: streamable-http  →  http://localhost:8000/mcp
```

### 4. Exponha o servidor com ngrok (para testes)

Em um **segundo terminal**:

```bash
# Instale o ngrok (uma vez só)
# Acesse https://ngrok.com, crie conta grátis e baixe

# Exponha o servidor
ngrok http 8000
```

O ngrok vai gerar uma URL como:
```
Forwarding: https://abc123.ngrok-free.app → localhost:8000
```

### 5. Registre no claude.ai

1. Acesse **claude.ai**
2. Vá em **Settings → Integrations**
3. Clique em **Add Integration**
4. Cole a URL: `https://abc123.ngrok-free.app/mcp`
5. Salve

---

## 💬 Exemplos de uso no Claude

Depois de configurado, você pode perguntar no chat:

```
"Liste todos os clientes da minha conta"
"Onde estão os veículos agora?"
"Quais veículos estão com a ignição ligada?"
"Busca o veículo de placa ABC1234"
"Mostra os dados da minha conta"
"Quantos veículos estão cadastrados?"
```

---

## 🔧 Adicionando novos endpoints

Para adicionar mais funcionalidades, crie um novo arquivo em `tools/` seguindo o padrão:

```python
# tools/minha_feature.py
from mcp.server.fastmcp import FastMCP
from utils.api_client import post, tratar_erro

def registrar_tools_minha_feature(mcp: FastMCP):

    @mcp.tool(name="nome_da_tool")
    async def nome_da_tool() -> str:
        """Descreva aqui o que a tool faz — o Claude lê isso para decidir quando usar."""
        try:
            resultado = await post("endpoint_da_api")
            # ... formata e retorna
        except Exception as e:
            return tratar_erro(e)
```

E registre no `server.py`:
```python
from tools.minha_feature import registrar_tools_minha_feature
registrar_tools_minha_feature(mcp)
```

---

## ⚠️ Segurança

- **Nunca** compartilhe o arquivo `.env`
- **Nunca** suba o `.env` para o Git (adicione ao `.gitignore`)
- O ngrok é apenas para testes — em produção use um host fixo (Railway, Render, VPS)
