/**
 * Local companion -> OpenClaw/Lilith proxy.
 *
 * Required env (no secrets in source):
 *   OPENCLAW_URL   e.g. http://127.0.0.1:3031   (or your remote Lilith proxy base URL)
 *   GATEWAY_TOKEN  Bearer token for the OpenClaw/Lilith gateway (optional if upstream has no auth)
 * Optional:
 *   PROXY_PORT     local listen port (default 3032)
 *
 * Example (PowerShell):
 *   $env:OPENCLAW_URL="http://127.0.0.1:3031"
 *   $env:GATEWAY_TOKEN="your-token-here"
 *   node proxy-server.cjs
 */
const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

const OPENCLAW_URL = (process.env.OPENCLAW_URL || '').replace(/\/$/, '');
const GATEWAY_TOKEN = process.env.GATEWAY_TOKEN || '';
const PROXY_PORT = Number(process.env.PROXY_PORT || 3032);

function redact(value) {
  if (value == null) return value;
  const s = typeof value === 'string' ? value : JSON.stringify(value);
  return s
    .replace(/(Bearer\s+)\S+/gi, '$1[REDACTED]')
    .replace(/(Token\s+)\S+/gi, '$1[REDACTED]')
    .replace(/(GATEWAY_TOKEN\s*[=:]\s*)\S+/gi, '$1[REDACTED]')
    .replace(/sk-[A-Za-z0-9_-]+/g, 'sk-[REDACTED]')
    .replace(/gsk_[A-Za-z0-9_-]+/g, 'gsk_[REDACTED]');
}



if (!OPENCLAW_URL) {
  console.error('[Proxy] FATAL: set OPENCLAW_URL (e.g. http://127.0.0.1:3031). Refusing to start with a hardcoded host.');
  process.exit(1);
}

// POST /api/command — Companion App'tan gelen mesajları OpenClaw'a gönder
app.post('/api/command', async (req, res) => {
  try {
    const { message, sender } = req.body;
    
    console.log(`[Proxy] Received message from ${sender}: "${message}"`);
    
    let openclaw_response;
    try {
      console.log('[Proxy] Sending to upstream at', OPENCLAW_URL);
      const headers = {
        'Content-Type': 'application/json'
      };
      if (GATEWAY_TOKEN) {
        headers['Authorization'] = `Bearer ${GATEWAY_TOKEN}`;
      }
      openclaw_response = await axios.post(`${OPENCLAW_URL}/api/command`, {
        message: message,
        sender: sender || 'WebUI'
      }, { headers });
      console.log('[Proxy] ✓ Response received from upstream');
    } catch (error) {
      console.log('[Proxy] ✗ Connection failed:');
      console.log('  Status:', error.response?.status);
      console.log('  Message:', error.message);
      console.log('  Data:', redact(error.response?.data));
      throw error;
    }
    
    const data = openclaw_response.data;
    console.log('[Proxy] OpenClaw response:', redact(data));
    
    const response_data = {
      text: data.text || data.message || data.response || 'Cevap alınamadı',
      emotion: data.emotion || 'neutral',
      original: data
    };
    
    console.log('[Proxy] Formatted response:', response_data);
    res.json(response_data);
    
  } catch (error) {
    console.error('[Proxy] Error:', redact(error.message));
    
    res.status(500).json({
      text: `Hata: ${error.message}`,
      emotion: 'sad',
      error: error.message
    });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Proxy is running',
    upstream_configured: Boolean(OPENCLAW_URL),
    auth_configured: Boolean(GATEWAY_TOKEN)
  });
});

app.listen(PROXY_PORT, '127.0.0.1', () => {
  console.log(`[Proxy] Server listening on http://127.0.0.1:${PROXY_PORT}`);
  console.log(`[Proxy] Forwarding to OpenClaw at ${OPENCLAW_URL}`);
  console.log(`[Proxy] Gateway auth: ${GATEWAY_TOKEN ? 'enabled (from GATEWAY_TOKEN)' : 'disabled'}`);
});
