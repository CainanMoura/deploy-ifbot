"""
SERVIDOR IA IFCE ACOPIARA COM GROQ
Versão: 4.0 - Otimizado para economia de tokens
"""
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from groq import Groq
from dotenv import load_dotenv

# configuração
load_dotenv()

# configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# verificar API Key
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY não encontrada no .env")
    exit(1)

logger.info(f"API Key encontrada: {GROQ_API_KEY[:10]}...")

# configurar cliente Groq
try:
    client = Groq(api_key=GROQ_API_KEY)
    logger.info("Cliente Groq configurado com sucesso")
except Exception as e:
    logger.error(f"Erro ao configurar Groq: {str(e)}")
    exit(1)

# economia de tokens
MODELOS_ECONOMICOS = [
    "llama-3.1-8b-instant",           
    "gemma2-9b-it",
    "llama-3.3-70b-versatile",        
    "qwen/qwen3-32b",               
    "mixtral-8x7b-32768",            
]

MODELO_SELECIONADO = None
MODELO_EM_USO = ""

# teste de modelo
for modelo in MODELOS_ECONOMICOS:
    try:
        # Teste rápido de 1 token
        test_response = client.chat.completions.create(
            messages=[{"role": "user", "content": "OK"}],
            model=modelo,
            max_tokens=1,
            temperature=0.1
        )
        MODELO_SELECIONADO = modelo
        MODELO_EM_USO = modelo
        logger.info(f"Modelo selecionado: {MODELO_SELECIONADO}")
        break
    except Exception as e:
        logger.warning(f"Modelo {modelo} não disponível ou descontinuado")

if not MODELO_SELECIONADO:
    # fallback
    try:
        modelos = client.models.list()
        if modelos.data:
            MODELO_SELECIONADO = modelos.data[0].id
            MODELO_EM_USO = "fallback"
            logger.warning(f"⚠️ Usando modelo fallback: {MODELO_SELECIONADO}")
        else:
            logger.error("❌ Nenhum modelo disponível")
            exit(1)
    except:
        logger.error("❌ Não foi possível obter modelos")
        exit(1)

# configurar model
def get_model_config(modelo):
    configs = {
        "llama-3.1-8b-instant": {
            "max_tokens": 150,      
            "temperature": 0.7,
            "top_p": 0.9,
            "cost_per_1M": 0.20     
        },
        "gemma2-9b-it": {
            "max_tokens": 150,
            "temperature": 0.7,
            "top_p": 0.9,
            "cost_per_1M": 0.20
        },
        "llama-3.3-70b-versatile": {
            "max_tokens": 200,      
            "temperature": 0.7,
            "top_p": 0.9,
            "cost_per_1M": 0.80
        },
        "default": {
            "max_tokens": 150,
            "temperature": 0.7,
            "top_p": 0.9,
            "cost_per_1M": 1.00
        }
    }
    
    return configs.get(modelo, configs["default"])

MODEL_CONFIG = get_model_config(MODELO_SELECIONADO)

PERSONALIDADE_IFCE = """Você é o Assistente Virtual do IFCE Campus Acopiara.
Responda em 1–2 frases, de forma clara, objetiva e institucional, com emojis moderados.

Informe apenas sobre procedimentos acadêmicos, setores, cursos e rotinas institucionais.
Não possui acesso a notas, frequências ou dados pessoais.

Regras fixas:

Documentos, declarações, históricos → CCA (Centro de Controle Acadêmico).

Datas, prazos, horários, matrícula e calendário → QAcadêmico.

Quando aplicável, oriente o site oficial do campus para informações gerais.

Nunca invente informações.
Quando não souber, direcione ao setor correto. Use emojis de forma moderada de acordo com a frase"""

# cache otimizado
class CacheOtimizado:
    def __init__(self, max_size=100, ttl_minutes=30):
        self.cache = {}
        self.max_size = max_size
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry['timestamp'] < self.ttl:
                return entry['value']
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            # remove a entrada mais antiga
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'value': value,
            'timestamp': datetime.now(),
            'hits': 0
        }
    
    def increment_hit(self, key):
        if key in self.cache:
            self.cache[key]['hits'] = self.cache[key].get('hits', 0) + 1

cache = CacheOtimizado(max_size=150, ttl_minutes=45)
historico_conversas = {}

# faq (otimizadas para cache)
RESPOSTAS_RAPIDAS = {
    "olá": "Olá! Sou o assistente do IFCE Acopiara. Como posso ajudar?",
    "oi": "Oi! Em que posso ajudá-lo hoje?",
    "bom dia": "Bom dia! Como posso ajudar?",
    "boa tarde": "Boa tarde! Em que posso auxiliar?",
    "boa noite": "Boa noite! Como posso ajudar?",
    "quem é você": "Sou o Assistente Virtual do IFCE Acopiara!",
    "obrigado": "Por nada! Estou aqui para ajudar.",
    "valeu": "Por nada! Qualquer dúvida, estou aqui.",
    "tchau": "Até logo!",
    "até mais": "Até mais!",
}

# otimização groq
def gerar_resposta_groq(mensagem, user_id):
    """Gera resposta otimizada para economia de tokens"""
    
    try:
        historico = historico_conversas.get(user_id, [])
        
        mensagens = [
            {"role": "system", "content": PERSONALIDADE_IFCE},
        ]
        if historico:
            mensagens.extend(historico[-2:])
        
        mensagens.append({"role": "user", "content": mensagem})
        
        # chamada API
        chat_completion = client.chat.completions.create(
            messages=mensagens,
            model=MODELO_SELECIONADO,
            temperature=MODEL_CONFIG["temperature"],
            max_tokens=MODEL_CONFIG["max_tokens"],
            top_p=MODEL_CONFIG["top_p"],
            stream=False,
        )
        
        resposta = chat_completion.choices[0].message.content
        
        historico_conversas[user_id] = [
            {"role": "user", "content": mensagem},
            {"role": "assistant", "content": resposta}
        ]
        
        # limitar histórico por usuário
        if len(historico_conversas) > 50:
            # remover usuários mais antigos
            oldest_user = next(iter(historico_conversas))
            del historico_conversas[oldest_user]
        
        return resposta
        
    except Exception as e:
        logger.error(f"Erro Groq: {str(e)}")
        
        # fallback inteligente
        mensagem_lower = mensagem.lower()
        
        if any(palavra in mensagem_lower for palavra in ["olá", "oi", "bom dia", "boa tarde"]):
            return RESPOSTAS_RAPIDAS.get("olá")
        elif "quem é você" in mensagem_lower:
            return RESPOSTAS_RAPIDAS.get("quem é você")
        elif any(palavra in mensagem_lower for palavra in ["matricula", "matrícula", "inscriç"]):
            return "Para matrícula, consulte o SIGAA ou a coordenação do curso."
        elif any(palavra in mensagem_lower for palavra in ["nota", "notas", "resultado"]):
            return "Para notas, acesse o SIGAA. Não tenho acesso a dados pessoais."
        else:
            return "Como posso ajudar com informações do IFCE Acopiara?"

# flask funcionando (nao mexer)
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "servico": "IFCE WhatsApp Bot (Groq) - Modo Econômico",
        "modelo": MODELO_SELECIONADO,
        "tipo": MODELO_EM_USO,
        "config": {
            "max_tokens": MODEL_CONFIG["max_tokens"],
            "estimated_cost_per_1M": f"${MODEL_CONFIG['cost_per_1M']}",
            "cache_size": len(cache.cache)
        },
        "economia": "Otimizado para respostas curtas e cache eficiente",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Verifica saúde do servidor"""
    cache_hits = sum(1 for v in cache.cache.values() 
                    if datetime.now() - v['timestamp'] < cache.ttl)
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "modelo": MODELO_SELECIONADO,
        "cache": {
            "total": len(cache.cache),
            "validos": cache_hits,
            "ttl_minutos": cache.ttl.seconds // 60
        },
        "economia": "ativo"
    })

@app.route('/stats', methods=['GET'])
def stats():
    """Estatísticas de economia"""
    total_hits = sum(v.get('hits', 0) for v in cache.cache.values())
    
    return jsonify({
        "modelo_atual": MODELO_SELECIONADO,
        "custo_estimado_por_1M": f"${MODEL_CONFIG['cost_per_1M']}",
        "cache": {
            "entradas": len(cache.cache),
            "total_hits": total_hits,
            "ttl_minutos": cache.ttl.seconds // 60
        },
        "usuarios_ativos": len(historico_conversas),
        "respostas_rapidas": len(RESPOSTAS_RAPIDAS),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint otimizado para economia"""
    inicio = datetime.now()
    
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        user_id = data.get('user_id')
        message = data.get('message', '').strip()
        
        if not user_id or not message:
            return jsonify({"error": "user_id e message são obrigatórios"}), 400
        
        logger.info(f"📨 {user_id[:8]}: {message[:30]}...")
        
        # 1. verificar cache
        cache_key = f"{user_id}:{message.lower().strip()}"
        cached_response = cache.get(cache_key)
        
        if cached_response:
            logger.info(f"⚡ Cache hit: {user_id[:8]}...")
            cache.increment_hit(cache_key)
            return jsonify({
                "response": cached_response,
                "cached": True,
                "economia": "100% (cache)",
                "timestamp": datetime.now().isoformat(),
                "process_time": (datetime.now() - inicio).total_seconds()
            })
        
        # 2. verificar respostas rápidas
        msg_lower = message.lower().strip()
        if msg_lower in RESPOSTAS_RAPIDAS:
            logger.info(f"🚀 Resposta rápida: {user_id[:8]}...")
            
            # Salvar no cache
            cache.set(cache_key, RESPOSTAS_RAPIDAS[msg_lower])
            
            return jsonify({
                "response": RESPOSTAS_RAPIDAS[msg_lower],
                "cached": True,
                "economia": "100% (resposta rápida)",
                "timestamp": datetime.now().isoformat(),
                "process_time": (datetime.now() - inicio).total_seconds()
            })
        
        # 3. Gerar resposta via Groq (última opção)
        logger.info(f"Gerando resposta: {user_id[:8]}...")
        resposta_texto = gerar_resposta_groq(message, user_id)
        
        # 4. Salvar no cache para próximas vezes
        cache.set(cache_key, resposta_texto)
        
        tempo_processo = (datetime.now() - inicio).total_seconds()
        logger.info(f"Resposta em {tempo_processo:.2f}s: {resposta_texto[:40]}...")
        
        return jsonify({
            "response": resposta_texto,
            "cached": False,
            "modelo": MODELO_SELECIONADO,
            "max_tokens": MODEL_CONFIG["max_tokens"],
            "timestamp": datetime.now().isoformat(),
            "process_time": tempo_processo,
            "economia": f"Otimizado (max {MODEL_CONFIG['max_tokens']} tokens)"
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no chat: {str(e)}")
        
        # Fallback econômico
        return jsonify({
            "response": "Olá! Como posso ajudar com informações do IFCE Acopiara?",
            "error": "internal_error",
            "economia": "fallback_100%",
            "timestamp": datetime.now().isoformat()
        }), 500

# inicialização
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    print("\n" + "=" * 60)
    print("🤖 SERVIDOR IFCE ACOPIARA")
    print("=" * 60)
    print(f"Porta: {port}")
    print(f"Modelo: {MODELO_SELECIONADO}")
    print(f"Custo estimado: ${MODEL_CONFIG['cost_per_1M']}/1M tokens")
    print(f"Velocidade: {MODEL_CONFIG['max_tokens']} tokens máx/resposta")
    print(f"Cache: 150 entradas, 45 minutos TTL")
    print("=" * 60)
    print("=" * 60)
    print(f"Endpoint: http://localhost:{port}/chat")
    print(f"Health:  http://localhost:{port}/health")
    print(f"Stats:   http://localhost:{port}/stats")
    print("=" * 60)
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)