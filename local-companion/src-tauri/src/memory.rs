//! Noctelle Phase 2 — local persistent memory (facts + tags).
//! Stored under %APPDATA%\OllamaGUI\memory.json

use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

static MEMORY: Lazy<Mutex<()>> = Lazy::new(|| Mutex::new(()));

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryFact {
    pub id: String,
    pub text: String,
    #[serde(default)]
    pub tags: Vec<String>,
    pub created_ms: u64,
    pub updated_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct MemoryFile {
    #[serde(default)]
    facts: Vec<MemoryFact>,
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn memory_path() -> PathBuf {
    let app_data = std::env::var("APPDATA").unwrap_or_else(|_| ".".into());
    let dir = PathBuf::from(app_data).join("OllamaGUI");
    let _ = fs::create_dir_all(&dir);
    dir.join("memory.json")
}

fn load_unlocked() -> MemoryFile {
    let path = memory_path();
    match fs::read_to_string(&path) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_default(),
        Err(_) => MemoryFile::default(),
    }
}

fn save_unlocked(store: &MemoryFile) -> Result<(), String> {
    let path = memory_path();
    let json = serde_json::to_string_pretty(store).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| format!("write memory failed: {}", e))
}

fn new_id() -> String {
    format!("m{}", now_ms())
}

/// Add a lasting fact. Returns the stored fact as JSON text.
pub fn memory_add(text: &str, tags: Vec<String>) -> Result<String, String> {
    let text = text.trim();
    if text.is_empty() {
        return Err("fact text is empty".into());
    }
    if text.len() > 500 {
        return Err("fact too long (max 500 chars)".into());
    }
    let _guard = MEMORY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    // Dedup near-identical text
    let lower = text.to_lowercase();
    if let Some(pos) = store
        .facts
        .iter()
        .position(|f| f.text.to_lowercase() == lower)
    {
        let summary = {
            let existing = &mut store.facts[pos];
            existing.updated_ms = now_ms();
            if !tags.is_empty() {
                for t in tags {
                    let tl = t.trim().to_lowercase();
                    if !tl.is_empty() && !existing.tags.iter().any(|x| x.eq_ignore_ascii_case(&tl)) {
                        existing.tags.push(tl);
                    }
                }
            }
            format!(
                "updated id={} tags={:?} text={}",
                existing.id, existing.tags, existing.text
            )
        };
        save_unlocked(&store)?;
        return Ok(summary);
    }
    let fact = MemoryFact {
        id: new_id(),
        text: text.to_string(),
        tags: tags
            .into_iter()
            .map(|t| t.trim().to_lowercase())
            .filter(|t| !t.is_empty())
            .collect(),
        created_ms: now_ms(),
        updated_ms: now_ms(),
    };
    let summary = format!("added id={} tags={:?} text={}", fact.id, fact.tags, fact.text);
    store.facts.push(fact);
    // Soft cap store size
    if store.facts.len() > 200 {
        store.facts.sort_by_key(|f| f.updated_ms);
        let drop_n = store.facts.len() - 200;
        store.facts.drain(0..drop_n);
    }
    save_unlocked(&store)?;
    Ok(summary)
}

/// Search / list facts. Empty query lists recent.
pub fn memory_search(query: &str, tag: Option<&str>, limit: usize) -> Result<String, String> {
    let _guard = MEMORY.lock().map_err(|e| e.to_string())?;
    let store = load_unlocked();
    let limit = limit.clamp(1, 40);
    let q = query.trim().to_lowercase();
    let tag_l = tag.map(|t| t.trim().to_lowercase()).filter(|t| !t.is_empty());

    let mut scored: Vec<(i64, &MemoryFact)> = store
        .facts
        .iter()
        .filter(|f| {
            if let Some(ref t) = tag_l {
                f.tags.iter().any(|x| x == t)
            } else {
                true
            }
        })
        .map(|f| {
            let mut score: i64 = (f.updated_ms / 1000) as i64; // recency base
            if !q.is_empty() {
                let hay = format!("{} {}", f.text.to_lowercase(), f.tags.join(" "));
                let mut hits = 0i64;
                for tok in q.split_whitespace() {
                    if tok.len() >= 2 && hay.contains(tok) {
                        hits += 10;
                    }
                }
                if hits == 0 && !hay.contains(&q) {
                    score = -1; // mark miss
                } else {
                    score += hits * 1000;
                }
            }
            (score, f)
        })
        .filter(|(s, _)| *s >= 0)
        .collect();

    scored.sort_by(|a, b| b.0.cmp(&a.0));
    scored.truncate(limit);

    if scored.is_empty() {
        return Ok("(no matching memories)".into());
    }
    let lines: Vec<String> = scored
        .iter()
        .map(|(_, f)| {
            let tags = if f.tags.is_empty() {
                String::new()
            } else {
                format!(" [{}]", f.tags.join(","))
            };
            format!("{}: {}{}", f.id, f.text, tags)
        })
        .collect();
    Ok(lines.join("\n"))
}

pub fn memory_list(limit: usize) -> Result<String, String> {
    memory_search("", None, limit)
}

/// Forget by id, or by substring match (first match / all if all=true).
pub fn memory_forget(id: Option<&str>, query: Option<&str>, all: bool) -> Result<String, String> {
    let _guard = MEMORY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    let before = store.facts.len();

    if let Some(id) = id.map(|s| s.trim()).filter(|s| !s.is_empty()) {
        store.facts.retain(|f| f.id != id);
    } else if let Some(q) = query.map(|s| s.trim().to_lowercase()).filter(|s| !s.is_empty()) {
        if all {
            store.facts.retain(|f| !f.text.to_lowercase().contains(&q));
        } else if let Some(pos) = store.facts.iter().position(|f| f.text.to_lowercase().contains(&q)) {
            store.facts.remove(pos);
        } else {
            return Ok("no matching memory to forget".into());
        }
    } else {
        return Err("provide id or query".into());
    }

    let removed = before.saturating_sub(store.facts.len());
    save_unlocked(&store)?;
    Ok(format!("forgot {} fact(s); {} remaining", removed, store.facts.len()))
}

/// Build a short memory block for system context injection (keyword + recency).
pub fn format_context_block(user_hint: &str, max_chars: usize) -> String {
    let max_chars = max_chars.clamp(200, 1200);
    let Ok(_guard) = MEMORY.lock() else {
        return String::new();
    };
    let store = load_unlocked();
    if store.facts.is_empty() {
        return String::new();
    }

    let q = user_hint.to_lowercase();
    let mut scored: Vec<(i64, &MemoryFact)> = store
        .facts
        .iter()
        .map(|f| {
            let mut score: i64 = (f.updated_ms / 60_000) as i64;
            if !q.is_empty() {
                let hay = format!(
                    "{} {}",
                    f.text.to_lowercase(),
                    f.tags.join(" ").to_lowercase()
                );
                for tok in q.split_whitespace().filter(|t| t.len() >= 3) {
                    if hay.contains(tok) {
                        score += 500;
                    }
                }
                // Prefer profile/prefs tags always a bit
                if f.tags.iter().any(|t| matches!(t.as_str(), "profile" | "prefs" | "projects")) {
                    score += 80;
                }
            } else if f.tags.iter().any(|t| matches!(t.as_str(), "profile" | "prefs")) {
                score += 200;
            }
            (score, f)
        })
        .collect();
    scored.sort_by(|a, b| b.0.cmp(&a.0));

    let mut out = String::from("Known lasting facts about Punk Milk (do not invent extras):\n");
    let header_len = out.len();
    let mut used = 0usize;
    for (_, f) in scored.iter().take(12) {
        let line = if f.tags.is_empty() {
            format!("- {}\n", f.text)
        } else {
            format!("- ({}) {}\n", f.tags.join("/"), f.text)
        };
        if header_len + used + line.len() > max_chars {
            break;
        }
        out.push_str(&line);
        used += line.len();
    }
    if used == 0 {
        return String::new();
    }
    out
}

pub fn memory_note_for_prompt() -> &'static str {
    "Memory: when the user shares lasting useful facts (name prefs, projects, routines), call memory_add. \
     Use memory_search before guessing personal details. Never invent memories. \
     Use memory_forget only when asked to forget something."
}

pub fn as_json_list(limit: usize) -> serde_json::Value {
    let Ok(_guard) = MEMORY.lock() else {
        return json!({"facts": []});
    };
    let mut store = load_unlocked();
    store.facts.sort_by_key(|f| std::cmp::Reverse(f.updated_ms));
    store.facts.truncate(limit.clamp(1, 100));
    json!({ "facts": store.facts, "path": memory_path().to_string_lossy() })
}
