/*
BOT WHATSAPP IFCE ACOPIARA
*/
require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const CONFIG = {
  SERVER_URL: 'http://localhost:5000',
  SESSION_DIR: process.env.WHATSAPP_SESSION_DIR || './wwebjs_auth',
  MAX_RETRIES: 3,
  REQUEST_TIMEOUT: 30000
};

const logger = {
  info: (msg) => console.log(`[${new Date().toLocaleTimeString()}] ${msg}`),
  success: (msg) => console.log(`[${new Date().toLocaleTimeString()}] ✅ ${msg}`),
  error: (msg) => console.error(`[${new Date().toLocaleTimeString()}] ❌ ${msg}`),
  warn: (msg) => console.warn(`[${new Date().toLocaleTimeString()}] ⚠️ ${msg}`)
};

logger.info('Iniciando Bot WhatsApp IFCE...');
const client = new Client({
  authStrategy: new LocalAuth({
    clientId: 'ifce-bot',
    dataPath: CONFIG.SESSION_DIR
  }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu'
    ]
  },
  webVersionCache: {
    type: 'remote',
    remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html'
  }
});

client.on('qr', (qr) => {
  console.log('\n' + '='.repeat(50));
  console.log('📱 ESCANEIE O QR CODE NO WHATSAPP');
  console.log('='.repeat(50));
  qrcode.generate(qr, { small: true });
  console.log('='.repeat(50));
  console.log('1. Abra WhatsApp → ⋮ → Dispositivos conectados');
  console.log('2. Toque em "Conectar dispositivo"');
  console.log('3. Aponte a câmera para o QR Code acima');
  console.log('='.repeat(50) + '\n');
});

client.on('authenticated', () => {
  logger.success('Autenticado no WhatsApp!');
});

client.on('ready', () => {
  logger.success('Bot WhatsApp está ONLINE!');
  console.log('\n' + '='.repeat(50));
  console.log('OK! BOT IFCE ACOPIARA PRONTO!');
  console.log('='.repeat(50));
  console.log('Agora você pode enviar mensagens para este número');
  console.log('O bot responderá automaticamente');
  console.log('Digite "sair" para desligar (apenas administrador)');
  console.log('='.repeat(50) + '\n');
});

client.on('auth_failure', (msg) => {
  logger.error(`Falha na autenticação: ${msg}`);
});

client.on('disconnected', (reason) => {
  logger.warn(`Desconectado: ${reason}`);
  logger.info('Reiniciando em 10 segundos...');
  setTimeout(() => client.initialize(), 10000);
});


client.on('message', async (msg) => {
  if (msg.from.includes('@g.us') || msg.from === 'status@broadcast') return;
  if (!msg.body || msg.body.trim() === '') return;


  if (msg.body.toLowerCase() === 'sair' && msg.from === 'ifbot@c.us') {
    await msg.reply('Desligando bot...');
    process.exit(0);
  }

  try {
    const usuario = msg.from.split('@')[0];
    logger.info(`📨 ${usuario}: ${msg.body.substring(0, 50)}...`);

    const chat = await msg.getChat();
    await chat.sendStateTyping();

    const resposta = await axios.post(
      `${CONFIG.SERVER_URL}/chat`,
      {
        user_id: msg.from,
        message: msg.body
      },
      {
        timeout: CONFIG.REQUEST_TIMEOUT,
        headers: { 'Content-Type': 'application/json' }
      }
    );

    await chat.clearState();

    if (resposta.data && resposta.data.response) {
      await msg.reply(resposta.data.response);
      logger.success(`Resposta enviada para ${usuario}`);
    } else {
      await msg.reply('❌ Não recebida resposta da IA. Tente novamente.');
      logger.warn(`Resposta vazia para ${usuario}`);
    }

  } catch (error) {
    logger.error(`Erro: ${error.message}`);

    try {
      if (error.code === 'ECONNREFUSED') {
        await msg.reply('Servidor IA offline. Aguarde...');
      } else if (error.response?.status === 500) {
        await msg.reply('Erro interno. Tente mais tarde.');
      } else {
        await msg.reply('Problema temporário. Aguarde um momento.');
      }
    } catch (e) {
      logger.error(`Falha ao enviar erro: ${e.message}`);
    }
  }
});

logger.info('Conectando ao WhatsApp Web...');
client.initialize();

process.on('SIGINT', async () => {
  logger.info('Desligando bot...');
  try {
    await client.destroy();
    logger.success('Bot desconectado');
    process.exit(0);
  } catch (error) {
    logger.error(`Erro ao desligar: ${error.message}`);
    process.exit(1);
  }
});

async function verificarServidor() {
  try {
    const resposta = await axios.get(`${CONFIG.SERVER_URL}/health`, {
      timeout: 5000
    });
    if (resposta.data.status === 'healthy') {
      logger.success('Servidor IA conectado');
      return true;
    }
  } catch (error) {
    logger.warn(`Servidor IA offline: ${error.message}`);
    logger.info('Certifique-se de executar: python servidor.py');
    return false;
  }
}

setInterval(verificarServidor, 300000);
verificarServidor();