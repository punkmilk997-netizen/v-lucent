//! Noctelle Phase 1 â€” tool registry + safe OS helpers.
//! Path allowlist, size caps, optional shell gate, and a small in-memory tool log.

use once_cell::sync::Lazy;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::env;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x08000000;
const MAX_READ_BYTES: u64 = 100 * 1024;
const MAX_LIST_ENTRIES: usize = 200;
const MAX_LOG: usize = 40;
const MAX_SEARCH_RESULTS: usize = 5;

static TOOL_LOG: Lazy<Mutex<VecDeque<ToolLogEntry>>> = Lazy::new(|| Mutex::new(VecDeque::new()));

#[derive(Clone, Debug, serde::Serialize)]
pub struct ToolLogEntry {
    pub ts_ms: u128,
    pub name: String,
    pub ok: bool,
    pub detail: String,
}

fn now_ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

pub fn push_log(name: &str, ok: bool, detail: impl Into<String>) {
    let entry = ToolLogEntry {
        ts_ms: now_ms(),
        name: name.to_string(),
        ok,
        detail: {
            let mut d = detail.into();
            if d.len() > 240 {
                d.truncate(237);
                d.push_str("...");
            }
            d
        },
    };
    if let Ok(mut q) = TOOL_LOG.lock() {
        q.push_back(entry);
        while q.len() > MAX_LOG {
            q.pop_front();
        }
    }
}

pub fn recent_log() -> Vec<ToolLogEntry> {
    TOOL_LOG
        .lock()
        .map(|q| q.iter().cloned().collect())
        .unwrap_or_default()
}

/// OpenAI-style tool schemas for native tool_calls (when the model supports them).
pub fn tool_schemas(allow_shell: bool) -> Vec<Value> {
    let mut tools = vec![
        tool_schema(
            "open_url",
            "Open a http/https URL in the default browser.",
            json!({
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL including https://"}
                },
                "required": ["url"]
            }),
        ),
        tool_schema(
            "open_path",
            "Open a file or folder under the allowlisted user folders (Desktop, Documents, Downloads, Desktop\\\\desktop-assistant).",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path or relative to Desktop/Documents/Downloads"}
                },
                "required": ["path"]
            }),
        ),
        tool_schema(
            "read_file",
            "Read a text file under allowlisted roots (max ~100KB).",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }),
        ),
        tool_schema(
            "list_dir",
            "List files/folders under an allowlisted directory. Use path 'Desktop', 'Documents', 'Downloads', or a full path under those roots.",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path or shortcut name like Desktop"}
                },
                "required": ["path"]
            }),
        ),
        tool_schema(
            "web_search",
            "Search the web (DuckDuckGo) and return top result snippets. Free, no API key.",
            json!({
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }),
        ),
        tool_schema(
            "memory_add",
            "Remember a lasting helpful fact about Punk Milk (prefs, projects, routines). Use short clear facts.",
            json!({
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags: profile, prefs, projects"}
                },
                "required": ["fact"]
            }),
        ),
        tool_schema(
            "memory_search",
            "Search or list stored memories. Empty query lists recent facts.",
            json!({
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tag": {"type": "string"},
                    "limit": {"type": "integer"}
                }
            }),
        ),
        tool_schema(
            "memory_forget",
            "Forget a stored memory by id or by matching query text.",
            json!({
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "query": {"type": "string"},
                    "all": {"type": "boolean", "description": "If true with query, remove all matches"}
                }
            }),
        ),
    ];
    if allow_shell {
        tools.push(tool_schema(
            "run_command",
            "Run a whitelisted safe shell command (dir, echo, whoami, hostname, ver, date). Destructive commands are blocked.",
            json!({
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command line starting with a whitelisted verb"},
                    "confirm": {"type": "boolean", "description": "Must be true to execute"}
                },
                "required": ["command", "confirm"]
            }),
        ));
    }
    tools
}

fn tool_schema(name: &str, description: &str, parameters: Value) -> Value {
    json!({
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters
        }
    })
}

/// Instructions appended for the JSON tool protocol (works without native tool_calls).
pub fn json_tool_protocol_prompt(allow_shell: bool) -> String {
    let mut tools = String::from(
        "Available tools:\n\
         - open_url {\"url\":\"https://...\"}\n\
         - open_path {\"path\":\"Desktop\" or full allowlisted path}\n\
         - read_file {\"path\":\"...\"}\n\
         - list_dir {\"path\":\"Desktop\"}\n\
         - web_search {\"query\":\"...\"}\n\
         - memory_add {\"fact\":\"...\",\"tags\":[\"prefs\"]}\n\
         - memory_search {\"query\":\"...\"}\n\
         - memory_forget {\"id\":\"m...\"} or {\"query\":\"...\"}\n",
    );
    if allow_shell {
        tools.push_str(
            "- run_command {\"command\":\"whoami\",\"confirm\":true}  (whitelist only; confirm required)\n",
        );
    }
    format!(
        "You can use tools to help Punk Milk. Keep your lil-sis wholesome voice in the FINAL reply only.\n\
         Do NOT narrate every tool step out loud â€” just use tools, then answer naturally in 1â€“3 sentences.\n\
         Ask before anything risky or outside the allowlist. Never reveal API keys or secrets.\n\
         Path allowlist: Desktop, Documents, Downloads, and Desktop\\desktop-assistant.\n\n\
         {tools}\n\
         When you need a tool, output one or more lines EXACTLY like:\n\
         TOOL_CALL: {{\"name\":\"list_dir\",\"arguments\":{{\"path\":\"Desktop\"}}}}\n\
         No other text on those lines. After tool results arrive, give your final natural-language answer \
         (optionally with a small emotion JSON as usual). If you do not need tools, reply normally."
    )
}

pub fn execute_tool(name: &str, args: &Value, allow_shell: bool) -> String {
    let started = Instant::now();
    let result = match name {
        "open_url" => tool_open_url(args),
        "open_path" => tool_open_path(args),
        "read_file" => tool_read_file(args),
        "list_dir" => tool_list_dir(args),
        "web_search" => tool_web_search(args),
        "memory_add" => tool_memory_add(args),
        "memory_search" => tool_memory_search(args),
        "memory_forget" => tool_memory_forget(args),
        "run_command" => {
            if !allow_shell {
                Err("run_command disabled (tools_allow_shell=false)".into())
            } else {
                tool_run_command(args)
            }
        }
        other => Err(format!("Unknown tool: {}", other)),
    };
    let ms = started.elapsed().as_millis();
    match result {
        Ok(text) => {
            push_log(name, true, format!("ok {}ms Â· {}", ms, brief(&text)));
            text
        }
        Err(err) => {
            push_log(name, false, format!("err {}ms Â· {}", ms, &err));
            format!("ERROR: {}", err)
        }
    }
}

fn brief(s: &str) -> String {
    s.chars().take(120).collect()
}

fn user_profile() -> PathBuf {
    env::var("USERPROFILE")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("C:\\Users\\Public"))
}

fn allowlist_roots() -> Vec<PathBuf> {
    let home = user_profile();
    let desktop = home.join("Desktop");
    vec![
        desktop.join("desktop-assistant"),
        desktop.clone(),
        home.join("Documents"),
        home.join("Downloads"),
    ]
}

fn resolve_user_path(raw: &str) -> Result<PathBuf, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("path is empty".into());
    }
    let lower = trimmed.to_lowercase();
    let home = user_profile();
    let candidate = match lower.as_str() {
        "desktop" | "~\\desktop" | "~/desktop" => home.join("Desktop"),
        "documents" | "~\\documents" | "~/documents" | "docs" => home.join("Documents"),
        "downloads" | "~\\downloads" | "~/downloads" => home.join("Downloads"),
        "desktop-assistant" | "desktop\\desktop-assistant" | "desktop/desktop-assistant" => {
            home.join("Desktop").join("desktop-assistant")
        }
        _ => {
            let p = PathBuf::from(trimmed);
            if p.is_absolute() {
                p
            } else {
                // Relative paths resolve under Desktop by default
                home.join("Desktop").join(trimmed)
            }
        }
    };
    let canon = if candidate.exists() {
        fs::canonicalize(&candidate).map_err(|e| format!("canonicalize failed: {}", e))?
    } else {
        // Allow opening/listing intent on missing paths only after allowlist check on parent
        candidate
    };
    ensure_allowlisted(&canon)?;
    Ok(canon)
}

fn ensure_allowlisted(path: &Path) -> Result<(), String> {
    let path_str = path.to_string_lossy().to_lowercase();
    // Block obvious secret locations even if somehow nested (they shouldn't be under allowlist)
    for bad in ["\\appdata\\", "\\.ssh", "\\.gnupg", "credentials", "secrets"] {
        if path_str.contains(bad) && !path_str.contains("desktop-assistant") {
            // APPDATA is outside allowlist anyway; keep message clear
            return Err(format!("Path blocked for safety: {}", path.display()));
        }
    }
    let roots = allowlist_roots();
    let mut root_canons: Vec<PathBuf> = Vec::new();
    for r in &roots {
        if let Ok(c) = fs::canonicalize(r) {
            root_canons.push(c);
        } else {
            root_canons.push(r.clone());
        }
    }
    // If path doesn't exist yet, check by string prefix against known roots
    let ok = root_canons.iter().any(|root| {
        path.starts_with(root)
            || path_str.starts_with(&root.to_string_lossy().to_lowercase())
    });
    if ok {
        Ok(())
    } else {
        Err(format!(
            "Path not in allowlist (Desktop / Documents / Downloads / Desktop\\\\desktop-assistant): {}",
            path.display()
        ))
    }
}

fn tool_open_url(args: &Value) -> Result<String, String> {
    let url = args
        .get("url")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing url".to_string())?
        .trim();
    let lower = url.to_lowercase();
    if !(lower.starts_with("http://") || lower.starts_with("https://")) {
        return Err("Only http:// or https:// URLs are allowed".into());
    }
    // Block file: and javascript:
    if lower.contains("file:") || lower.contains("javascript:") {
        return Err("Disallowed URL scheme".into());
    }
    open_with_shell(url)?;
    Ok(format!("Opened URL in default browser: {}", url))
}

fn tool_open_path(args: &Value) -> Result<String, String> {
    let raw = args
        .get("path")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing path".to_string())?;
    let path = resolve_user_path(raw)?;
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }
    open_with_shell(&path.to_string_lossy())?;
    Ok(format!("Opened: {}", path.display()))
}

fn open_with_shell(target: &str) -> Result<(), String> {
    #[cfg(windows)]
    {
        // `start` treats first quoted arg as window title â€” pass empty title.
        let status = Command::new("cmd")
            .args(["/C", "start", "", target])
            .creation_flags(CREATE_NO_WINDOW)
            .status()
            .map_err(|e| format!("ShellExecute failed: {}", e))?;
        if status.success() {
            Ok(())
        } else {
            Err(format!("start exited with {:?}", status.code()))
        }
    }
    #[cfg(not(windows))]
    {
        let _ = target;
        Err("open only supported on Windows".into())
    }
}

fn tool_read_file(args: &Value) -> Result<String, String> {
    let raw = args
        .get("path")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing path".to_string())?;
    let path = resolve_user_path(raw)?;
    if !path.is_file() {
        return Err(format!("Not a file: {}", path.display()));
    }
    let meta = fs::metadata(&path).map_err(|e| e.to_string())?;
    if meta.len() > MAX_READ_BYTES {
        return Err(format!(
            "File too large ({} bytes > {} cap)",
            meta.len(),
            MAX_READ_BYTES
        ));
    }
    let mut f = fs::File::open(&path).map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).map_err(|e| e.to_string())?;
    // Reject likely-binary
    let nul = buf.iter().filter(|b| **b == 0).count();
    if nul > 0 {
        return Err("Refusing to read binary file".into());
    }
    let text = String::from_utf8_lossy(&buf).to_string();
    Ok(format!("--- {} ---\n{}", path.display(), text))
}

fn tool_list_dir(args: &Value) -> Result<String, String> {
    let raw = args
        .get("path")
        .and_then(|v| v.as_str())
        .unwrap_or("Desktop");
    let path = resolve_user_path(raw)?;
    if !path.is_dir() {
        return Err(format!("Not a directory: {}", path.display()));
    }
    let mut entries: Vec<String> = Vec::new();
    let rd = fs::read_dir(&path).map_err(|e| e.to_string())?;
    for (i, ent) in rd.enumerate() {
        if i >= MAX_LIST_ENTRIES {
            entries.push(format!("... truncated at {} entries", MAX_LIST_ENTRIES));
            break;
        }
        let ent = ent.map_err(|e| e.to_string())?;
        let name = ent.file_name().to_string_lossy().to_string();
        let kind = if ent.path().is_dir() { "dir" } else { "file" };
        entries.push(format!("[{}] {}", kind, name));
    }
    entries.sort();
    Ok(format!(
        "Listing {} ({} items):\n{}",
        path.display(),
        entries.len(),
        entries.join("\n")
    ))
}

fn url_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len() * 2);
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            b' ' => out.push_str("+"),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

fn tool_web_search(args: &Value) -> Result<String, String> {
    let query = args
        .get("query")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing query".to_string())?
        .trim();
    if query.is_empty() {
        return Err("query is empty".into());
    }
    let url = format!(
        "https://html.duckduckgo.com/html/?q={}",
        url_encode(query)
    );
    // Blocking HTTP via reqwest::blocking isn't available (async runtime). Use a tiny sync-ish approach:
    // spawn a short-lived runtime... but we're already inside tokio. Use std::thread + reqwest blocking alternative:
    // reqwest Client in block_in_place / Handle::current().block_on won't work nested easily.
    // Use `ureq`-less approach: std Command curl if present, else spawn thread with its own runtime.

    let html = fetch_url_blocking(&url)?;
    let snippets = parse_ddg_html(&html);
    if snippets.is_empty() {
        // Brittle scrape fallback: open search in browser
        let open_url = format!("https://duckduckgo.com/?q={}", url_encode(query));
        let _ = open_with_shell(&open_url);
        return Ok(format!(
            "No parseable snippets (DDG HTML may have changed). Opened search in browser for: {}",
            query
        ));
    }
    let mut out = format!("Search results for \"{}\":\n", query);
    for (i, (title, snippet, href)) in snippets.iter().take(MAX_SEARCH_RESULTS).enumerate() {
        out.push_str(&format!(
            "{}. {}\n   {}\n   {}\n",
            i + 1,
            title,
            snippet,
            href
        ));
    }
    Ok(out)
}

fn fetch_url_blocking(url: &str) -> Result<String, String> {
    let url = url.to_string();
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| e.to_string())?;
        rt.block_on(async move {
            let client = reqwest::Client::builder()
                .timeout(Duration::from_secs(12))
                .user_agent("NoctelleCompanion/1.0 (desktop; +local)")
                .build()
                .map_err(|e| e.to_string())?;
            let resp = client
                .get(&url)
                .send()
                .await
                .map_err(|e| format!("search fetch failed: {}", e))?;
            if !resp.status().is_success() {
                return Err(format!("search HTTP {}", resp.status()));
            }
            resp.text()
                .await
                .map_err(|e| format!("search body: {}", e))
        })
    })
    .join()
    .map_err(|_| "search thread panicked".to_string())?
}

fn strip_tags(s: &str) -> String {
    let mut out = String::new();
    let mut in_tag = false;
    for c in s.chars() {
        match c {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => out.push(c),
            _ => {}
        }
    }
    html_decode(&out)
}

fn html_decode(s: &str) -> String {
    s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
}

fn parse_ddg_html(html: &str) -> Vec<(String, String, String)> {
    let mut results = Vec::new();
    // Very small heuristic parser for result__a / result__snippet
    let mut rest = html;
    while let Some(idx) = rest.find("result__a") {
        rest = &rest[idx..];
        let href = extract_after(rest, "href=\"", "\"").unwrap_or_default();
        let title_raw = extract_between(rest, ">", "</a>").unwrap_or_default();
        let title = strip_tags(&title_raw).trim().to_string();
        let after = rest.get(0..).unwrap_or(rest);
        let snippet = if let Some(sidx) = after.find("result__snippet") {
            let sn = &after[sidx..];
            let raw = extract_between(sn, ">", "</").unwrap_or_default();
            strip_tags(&raw).trim().to_string()
        } else {
            String::new()
        };
        if !title.is_empty() {
            results.push((title, snippet, href.to_string()));
        }
        if results.len() >= MAX_SEARCH_RESULTS {
            break;
        }
        rest = rest.get(10..).unwrap_or("");
    }
    results
}

fn extract_after<'a>(s: &'a str, start: &str, end: &str) -> Option<&'a str> {
    let i = s.find(start)? + start.len();
    let rest = s.get(i..)?;
    let j = rest.find(end)?;
    rest.get(..j)
}

fn extract_between<'a>(s: &'a str, start: &str, end: &str) -> Option<&'a str> {
    let i = s.find(start)? + start.len();
    let rest = s.get(i..)?;
    let j = rest.find(end)?;
    rest.get(..j)
}

const SHELL_WHITELIST: &[&str] = &["dir", "echo", "whoami", "hostname", "ver", "date"];

fn tool_run_command(args: &Value) -> Result<String, String> {
    let confirm = args.get("confirm").and_then(|v| v.as_bool()).unwrap_or(false);
    if !confirm {
        return Err("run_command requires confirm=true".into());
    }
    let cmd = args
        .get("command")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing command".to_string())?
        .trim();
    if cmd.is_empty() {
        return Err("command is empty".into());
    }
    // Reject shell metacharacters that chain/redirect
    for bad in ['|', '&', '>', '<', '`', '\n', '\r', ';'] {
        if cmd.contains(bad) {
            return Err(format!("Blocked shell metacharacter: {:?}", bad));
        }
    }
    let first = cmd.split_whitespace().next().unwrap_or("");
    let first_l = first.to_lowercase();
    if !SHELL_WHITELIST.iter().any(|w| *w == first_l) {
        return Err(format!(
            "Command '{}' not whitelisted. Allowed: {}",
            first,
            SHELL_WHITELIST.join(", ")
        ));
    }
    #[cfg(windows)]
    {
        let output = Command::new("cmd")
            .args(["/C", cmd])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map_err(|e| format!("failed to run: {}", e))?;
        let mut text = String::from_utf8_lossy(&output.stdout).to_string();
        let err = String::from_utf8_lossy(&output.stderr);
        if !err.trim().is_empty() {
            text.push_str("\n");
            text.push_str(&err);
        }
        if text.len() > 8000 {
            text.truncate(8000);
            text.push_str("\n...truncated");
        }
        Ok(format!(
            "exit {:?} Â· output:\n{}",
            output.status.code(),
            text
        ))
    }
    #[cfg(not(windows))]
    {
        Err("run_command only on Windows".into())
    }
}

/// Parse TOOL_CALL lines from model text (JSON protocol).

fn tool_memory_add(args: &Value) -> Result<String, String> {
    let fact = args
        .get("fact")
        .or_else(|| args.get("text"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let tags: Vec<String> = args
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();
    crate::memory::memory_add(&fact, tags)
}

fn tool_memory_search(args: &Value) -> Result<String, String> {
    let query = args.get("query").and_then(|v| v.as_str()).unwrap_or("");
    let tag = args.get("tag").and_then(|v| v.as_str());
    let limit = args
        .get("limit")
        .and_then(|v| v.as_u64())
        .unwrap_or(8) as usize;
    crate::memory::memory_search(query, tag, limit)
}

fn tool_memory_forget(args: &Value) -> Result<String, String> {
    let id = args.get("id").and_then(|v| v.as_str());
    let query = args.get("query").and_then(|v| v.as_str());
    let all = args.get("all").and_then(|v| v.as_bool()).unwrap_or(false);
    crate::memory::memory_forget(id, query, all)
}
pub fn parse_tool_calls_from_text(text: &str) -> Vec<(String, Value)> {
    let mut calls = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim();
        let payload = if let Some(rest) = trimmed.strip_prefix("TOOL_CALL:") {
            rest.trim()
        } else if let Some(rest) = trimmed.strip_prefix("tool_call:") {
            rest.trim()
        } else {
            continue;
        };
        if let Ok(v) = serde_json::from_str::<Value>(payload) {
            if let Some(name) = v.get("name").and_then(|n| n.as_str()) {
                let args = v.get("arguments").cloned().unwrap_or_else(|| json!({}));
                calls.push((name.to_string(), args));
            }
        }
    }
    // Also accept a fenced JSON block: ```json {"tool":"...","args":{}} ```
    if calls.is_empty() {
        if let Some(start) = text.find("{\"name\"") {
            if let Some(end) = text[start..].find('}') {
                // try to parse a single object â€” greedy expand for nested args
                if let Some(obj) = extract_json_object(&text[start..]) {
                    if let Some(name) = obj.get("name").and_then(|n| n.as_str()) {
                        let args = obj.get("arguments").cloned().unwrap_or_else(|| json!({}));
                        calls.push((name.to_string(), args));
                    }
                }
                let _ = end;
            }
        }
    }
    calls
}

fn extract_json_object(s: &str) -> Option<Value> {
    let bytes = s.as_bytes();
    if bytes.first() != Some(&b'{') {
        return None;
    }
    let mut depth = 0i32;
    for (i, b) in bytes.iter().enumerate() {
        match b {
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    return serde_json::from_str(&s[..=i]).ok();
                }
            }
            _ => {}
        }
    }
    None
}

/// Strip TOOL_CALL lines and leftover protocol noise for the final spoken reply.
pub fn strip_tool_protocol(text: &str) -> String {
    let mut lines: Vec<&str> = Vec::new();
    for line in text.lines() {
        let t = line.trim();
        if t.starts_with("TOOL_CALL:") || t.starts_with("tool_call:") {
            continue;
        }
        lines.push(line);
    }
    lines.join("\n").trim().to_string()
}
