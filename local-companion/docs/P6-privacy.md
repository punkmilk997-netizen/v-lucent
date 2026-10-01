# P6 — Polish & privacy

## Path allowlist (OneDrive-safe)

Tool path helpers (`open_path` / `read_file` / `list_dir`) resolve **Desktop / Documents / Downloads** via Windows **Known Folder APIs** (`SHGetKnownFolderPath`), not only `%USERPROFILE%\Desktop`.

Also included when present on disk:

- Classic `%USERPROFILE%\{Desktop,Documents,Downloads}`
- `%OneDrive%`, `%OneDriveConsumer%`, `%OneDriveCommercial%` subfolders of the same names
- `Desktop\desktop-assistant`

This keeps redirected OneDrive folders inside the allowlist after canonicalize.

## Log redaction

`privacy::redact_secrets` strips API keys, Bearer/Token headers, `GATEWAY_TOKEN=…`, and common `sk-` / `gsk_` prefixes from:

- tool activity log details
- high-risk backend log lines (vision spawn, capture body samples, HTTP error payloads)
- `proxy-server.cjs` error/response dumps

## Tauri CSP

`tauri.conf.json` sets a non-null CSP that still allows:

- local backends (`http://127.0.0.1:*`, `localhost`)
- VRM/Three blob URLs + TTS `blob:` audio
- Deepgram / OpenAI / ElevenLabs / Groq / OpenRouter HTTPS
- Tauri IPC (`ipc:`, `http://ipc.localhost`)

If a future provider needs another host, add it explicitly to `connect-src`.

## Local Ollama (offline path)

When **API type = Ollama**:

1. Run Ollama locally (`ollama serve`; default `http://127.0.0.1:11434`).
2. In Settings, set **Ollama Endpoint** to that URL (empty endpoint also falls back to `http://127.0.0.1:11434` in the Rust backend).
3. Pick a pulled model (e.g. `mistral`, `llama3.2`).
4. No cloud API key is required for the Ollama provider path — chat goes to `/ollama-chat` → native `/api/chat`.

Vision/STT/TTS features that still point at cloud providers need their own keys; they are independent of the Ollama chat path.

## Installer gap

`tauri.conf.json` has **no `bundle` / NSIS / MSI** section yet. `npm run tauri build` produces a release binary under `src-tauri/target/release/`, but a polished installer (icons, shortcuts, WebView2 bootstrapper) is **not** wired. Deferred — do not boil the ocean in P6.

## Shell gate

`tools_allow_shell` default remains **`false`**.