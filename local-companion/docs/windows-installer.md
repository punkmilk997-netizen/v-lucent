# Windows installer build (Tauri 2)

## Prerequisites
- Node.js + npm (repo `local-companion`)
- Rust toolchain (`rustc` / `cargo`)
- Tauri CLI (`npx tauri` or global `@tauri-apps/cli`)
- WebView2 runtime (Win10/11 usually present; installer can download bootstrapper)
- For MSI: WiX Toolset v3 (Tauri bundler fetches/uses as needed); Windows optional feature VBSCRIPT if `light.exe` fails

## Config
`src-tauri/tauri.conf.json` → `bundle.active=true`, `bundle.targets=["nsis","msi"]`, icon `icons/icon.ico`.
NSIS install mode: `currentUser` (no admin). WebView2: `downloadBootstrapper`.

App setting `tools_allow_shell` remains **false** by default in code; packaging uses normal host shell commands only for the build itself.

## Build command
From `local-companion`:

```bat
npm run tauri build
```

Artifacts (typical):
- NSIS: `src-tauri/target/release/bundle/nsis/*-setup.exe`
- MSI:  `src-tauri/target/release/bundle/msi/*.msi`

NSIS-only (faster / fewer deps):

```bat
npm run tauri build -- --bundles nsis
```
