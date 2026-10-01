/**
 * Dev proxy to a local OpenClaw instance.
 *
 * Env (optional):
 *   OPENCLAW_URL  default http://127.0.0.1:18789
 *   PROXY_PORT    default 3031
 */
const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

const OPENCLAW_URL = (process.env.OPENCLAW_URL || 'http://127.0.0.1:18789').replace(/\/$/, '');
const PROXY_PORT = Number(process.env.PROXY_PORT || 3031);

// POST /api/command — Companion App'tan gelen mesajları OpenClaw'a gönder
app.post('/api/command', async (req, res) => {
  try {
    const { message, sender } = req.body;
    
    console.log(`[Proxy] Received message from ${sender}: "${message}"`);
    
    const openclaw_response = await axios.post(`${OPENCLAW_URL}/sessions_send`, {
      message: message,
      sender: sender || 'WebUI'
    }).catch(async (error) => {
      console.log('[Proxy] sessions_send failed, trying /api/command...');
      return axios.post(`${OPENCLAW_URL}/api/command`, {
        message: message,
        sender: sender || 'WebUI'
      });
    });
    
    const data = openclaw_response.data;
    console.log('[Proxy] OpenClaw response:', data);
    
    const response_data = {
      text: data.text || data.message || data.response || 'Cevap alınamadı',
      emotion: data.emotion || 'neutral',
      original: data
    };
    
    console.log('[Proxy] Formatted response:', response_data);
    res.json(response_data);
    
  } catch (error) {
    console.error('[Proxy] Error:', error.message);
    
    res.status(500).json({
      text: `Hata: ${error.message}`,
      emotion: 'sad',
      error: error.message
    });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Proxy is running' });
});

app.listen(PROXY_PORT, '127.0.0.1', () => {
  console.log(`[Proxy] Server listening on http://127.0.0.1:${PROXY_PORT}`);
  console.log(`[Proxy] Forwarding to OpenClaw at ${OPENCLAW_URL}`);
});
