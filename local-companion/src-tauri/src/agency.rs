//! Noctelle Phase 5 — agency reminders / watchers with explicit user consent.
//! Schedule + consent persist under %APPDATA%\OllamaGUI\agency.json
//! Nothing fires without consent; each item fires at most once.

use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

static AGENCY: Lazy<Mutex<()>> = Lazy::new(|| Mutex::new(()));
static PATH_OVERRIDE: Lazy<Mutex<Option<PathBuf>>> = Lazy::new(|| Mutex::new(None));

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum AgencyKind {
    Reminder,
    Watcher,
}

impl AgencyKind {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s.trim().to_lowercase().as_str() {
            "reminder" => Ok(AgencyKind::Reminder),
            "watcher" => Ok(AgencyKind::Watcher),
            other => Err(format!("unknown kind '{}'; use reminder|watcher", other)),
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            AgencyKind::Reminder => "reminder",
            AgencyKind::Watcher => "watcher",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum AgencyStatus {
    Pending,
    Fired,
    Cancelled,
}

impl Default for AgencyStatus {
    fn default() -> Self {
        AgencyStatus::Pending
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgencyItem {
    pub id: String,
    pub kind: AgencyKind,
    pub title: String,
    pub message: String,
    /// Unix epoch millis when the item becomes due.
    pub fire_at_ms: u64,
    #[serde(default)]
    pub status: AgencyStatus,
    pub created_ms: u64,
    #[serde(default)]
    pub fired_ms: Option<u64>,
    #[serde(default)]
    pub cancelled_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FireRecord {
    pub id: String,
    pub title: String,
    pub message: String,
    pub fired_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct AgencyFile {
    /// Explicit user consent — agency is silent/off until true.
    #[serde(default)]
    consent: bool,
    #[serde(default)]
    consent_at_ms: Option<u64>,
    #[serde(default)]
    items: Vec<AgencyItem>,
    #[serde(default)]
    fire_log: Vec<FireRecord>,
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

/// Test/harness helper: redirect persistence path (None restores default).
pub fn set_path_override(path: Option<PathBuf>) {
    if let Ok(mut g) = PATH_OVERRIDE.lock() {
        *g = path;
    }
}

fn agency_path() -> PathBuf {
    if let Ok(g) = PATH_OVERRIDE.lock() {
        if let Some(ref p) = *g {
            return p.clone();
        }
    }
    let app_data = std::env::var("APPDATA").unwrap_or_else(|_| ".".into());
    let dir = PathBuf::from(app_data).join("OllamaGUI");
    let _ = fs::create_dir_all(&dir);
    dir.join("agency.json")
}

fn load_unlocked() -> AgencyFile {
    let path = agency_path();
    match fs::read_to_string(&path) {
        Ok(mut s) => {
            if s.starts_with('\u{feff}') {
                s = s.trim_start_matches('\u{feff}').to_string();
            }
            serde_json::from_str(&s).unwrap_or_default()
        }
        Err(_) => AgencyFile::default(),
    }
}

fn save_unlocked(store: &AgencyFile) -> Result<(), String> {
    let path = agency_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let json = serde_json::to_string_pretty(store).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| format!("write agency failed: {}", e))
}

fn new_id(prefix: &str) -> String {
    format!("{}{}", prefix, now_ms())
}

pub fn has_consent() -> bool {
    let Ok(_guard) = AGENCY.lock() else {
        return false;
    };
    load_unlocked().consent
}

pub fn set_consent(consent: bool) -> Result<serde_json::Value, String> {
    let _guard = AGENCY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    store.consent = consent;
    store.consent_at_ms = if consent { Some(now_ms()) } else { store.consent_at_ms };
    // Revoking consent cancels all pending items so nothing fires silently later.
    if !consent {
        let t = now_ms();
        for item in store.items.iter_mut() {
            if item.status == AgencyStatus::Pending {
                item.status = AgencyStatus::Cancelled;
                item.cancelled_ms = Some(t);
            }
        }
    }
    save_unlocked(&store)?;
    Ok(json!({
        "consent": store.consent,
        "consent_at_ms": store.consent_at_ms,
        "path": agency_path().to_string_lossy(),
    }))
}

fn require_consent(store: &AgencyFile) -> Result<(), String> {
    if store.consent {
        Ok(())
    } else {
        Err("agency consent required — enable Agency in Settings first (not silent)".into())
    }
}

/// Create a one-shot reminder or watcher. Requires consent.
pub fn create(
    kind: &str,
    title: &str,
    message: &str,
    fire_at_ms: u64,
) -> Result<AgencyItem, String> {
    let kind = AgencyKind::parse(kind)?;
    let title = title.trim();
    let message = message.trim();
    if title.is_empty() {
        return Err("title is empty".into());
    }
    if title.len() > 120 {
        return Err("title too long (max 120)".into());
    }
    if message.len() > 500 {
        return Err("message too long (max 500)".into());
    }
    let _guard = AGENCY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    require_consent(&store)?;
    if store.items.iter().filter(|i| i.status == AgencyStatus::Pending).count() >= 40 {
        return Err("too many pending agency items (max 40)".into());
    }
    let item = AgencyItem {
        id: new_id(match kind {
            AgencyKind::Reminder => "r",
            AgencyKind::Watcher => "w",
        }),
        kind,
        title: title.to_string(),
        message: if message.is_empty() {
            title.to_string()
        } else {
            message.to_string()
        },
        fire_at_ms,
        status: AgencyStatus::Pending,
        created_ms: now_ms(),
        fired_ms: None,
        cancelled_ms: None,
    };
    store.items.push(item.clone());
    save_unlocked(&store)?;
    Ok(item)
}

pub fn list(include_done: bool) -> Result<Vec<AgencyItem>, String> {
    let _guard = AGENCY.lock().map_err(|e| e.to_string())?;
    let store = load_unlocked();
    let mut items = store.items;
    if !include_done {
        items.retain(|i| i.status == AgencyStatus::Pending);
    }
    items.sort_by_key(|i| i.fire_at_ms);
    Ok(items)
}

pub fn cancel(id: &str) -> Result<String, String> {
    let id = id.trim();
    if id.is_empty() {
        return Err("id is empty".into());
    }
    let _guard = AGENCY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    let Some(item) = store.items.iter_mut().find(|i| i.id == id) else {
        return Err(format!("no agency item with id {}", id));
    };
    match item.status {
        AgencyStatus::Cancelled => Ok(format!("already cancelled {}", id)),
        AgencyStatus::Fired => Err(format!("cannot cancel already-fired {}", id)),
        AgencyStatus::Pending => {
            item.status = AgencyStatus::Cancelled;
            item.cancelled_ms = Some(now_ms());
            save_unlocked(&store)?;
            Ok(format!("cancelled {}", id))
        }
    }
}

/// Fire all due pending items once. No-op without consent (returns empty).
/// Controlled tests pass an explicit `now_ms`.
pub fn tick(now: u64) -> Result<Vec<FireRecord>, String> {
    let _guard = AGENCY.lock().map_err(|e| e.to_string())?;
    let mut store = load_unlocked();
    if !store.consent {
        return Ok(Vec::new());
    }
    let mut fired = Vec::new();
    for item in store.items.iter_mut() {
        if item.status == AgencyStatus::Pending && item.fire_at_ms <= now {
            item.status = AgencyStatus::Fired;
            item.fired_ms = Some(now);
            let rec = FireRecord {
                id: item.id.clone(),
                title: item.title.clone(),
                message: item.message.clone(),
                fired_ms: now,
            };
            fired.push(rec.clone());
            store.fire_log.push(rec);
        }
    }
    if store.fire_log.len() > 80 {
        let drop_n = store.fire_log.len() - 80;
        store.fire_log.drain(0..drop_n);
    }
    if !fired.is_empty() {
        save_unlocked(&store)?;
    }
    Ok(fired)
}

pub fn status_json() -> serde_json::Value {
    let Ok(_guard) = AGENCY.lock() else {
        return json!({"consent": false, "error": "lock"});
    };
    let store = load_unlocked();
    let pending = store
        .items
        .iter()
        .filter(|i| i.status == AgencyStatus::Pending)
        .count();
    json!({
        "consent": store.consent,
        "consent_at_ms": store.consent_at_ms,
        "pending": pending,
        "total": store.items.len(),
        "fire_log_len": store.fire_log.len(),
        "path": agency_path().to_string_lossy(),
        "tools_allow_shell": false,
    })
}

pub fn as_json(include_done: bool) -> serde_json::Value {
    let Ok(items) = list(include_done) else {
        return json!({"consent": false, "items": []});
    };
    let Ok(_guard) = AGENCY.lock() else {
        return json!({"consent": false, "items": []});
    };
    let store = load_unlocked();
    json!({
        "consent": store.consent,
        "consent_at_ms": store.consent_at_ms,
        "items": items,
        "fire_log": store.fire_log.iter().rev().take(20).cloned().collect::<Vec<_>>(),
        "path": agency_path().to_string_lossy(),
    })
}

pub fn agency_note_for_prompt() -> &'static str {
    "Agency: only schedule reminders/watchers when the user has enabled Agency consent in Settings. \
     Use agency_create for timed one-shot reminders; agency_list to show pending; agency_cancel to stop one. \
     Never schedule silently — if consent is off, ask the user to turn Agency on."
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex as StdMutex;

    static TEST_LOCK: StdMutex<()> = StdMutex::new(());

    fn with_temp<F: FnOnce(PathBuf)>(f: F) {
        let _lock = TEST_LOCK.lock().unwrap();
        let dir = std::env::temp_dir().join(format!("noctelle_agency_test_{}", now_ms()));
        let _ = fs::create_dir_all(&dir);
        let path = dir.join("agency.json");
        set_path_override(Some(path.clone()));
        // fresh file
        let _ = fs::remove_file(&path);
        f(path.clone());
        set_path_override(None);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn no_create_without_consent() {
        with_temp(|_p| {
            assert!(!has_consent());
            let err = create("reminder", "stretch", "stand up", now_ms() + 1000).unwrap_err();
            assert!(err.to_lowercase().contains("consent"));
        });
    }

    #[test]
    fn create_persist_fire_once_cancel() {
        with_temp(|path| {
            set_consent(true).unwrap();
            assert!(has_consent());

            let t0 = 1_000_000u64;
            let item = create("reminder", "hydrate", "drink water", t0 + 5_000).unwrap();
            assert_eq!(item.status, AgencyStatus::Pending);
            assert!(path.exists());

            // Not due yet
            let fired = tick(t0 + 1_000).unwrap();
            assert!(fired.is_empty());
            assert_eq!(list(false).unwrap().len(), 1);

            // Due → fires once
            let fired = tick(t0 + 5_000).unwrap();
            assert_eq!(fired.len(), 1);
            assert_eq!(fired[0].id, item.id);
            assert_eq!(fired[0].title, "hydrate");

            // Second tick does not re-fire
            let fired2 = tick(t0 + 9_000).unwrap();
            assert!(fired2.is_empty());
            assert!(list(false).unwrap().is_empty());
            let all = list(true).unwrap();
            assert_eq!(all.len(), 1);
            assert_eq!(all[0].status, AgencyStatus::Fired);

            // Cancel path on a fresh pending item
            let item2 = create("watcher", "build", "check CI", t0 + 60_000).unwrap();
            let msg = cancel(&item2.id).unwrap();
            assert!(msg.contains("cancelled"));
            let pending = list(false).unwrap();
            assert!(pending.iter().all(|i| i.id != item2.id));
            let again = cancel(&item2.id).unwrap();
            assert!(again.contains("already cancelled"));

            // Cannot cancel fired
            let err = cancel(&item.id).unwrap_err();
            assert!(err.contains("already-fired") || err.contains("cannot cancel"));
        });
    }

    #[test]
    fn revoke_consent_cancels_pending() {
        with_temp(|_p| {
            set_consent(true).unwrap();
            let item = create("reminder", "later", "msg", now_ms() + 99_000).unwrap();
            set_consent(false).unwrap();
            assert!(!has_consent());
            let all = list(true).unwrap();
            let found = all.iter().find(|i| i.id == item.id).unwrap();
            assert_eq!(found.status, AgencyStatus::Cancelled);
            // tick does nothing without consent
            let fired = tick(now_ms() + 200_000).unwrap();
            assert!(fired.is_empty());
        });
    }

    #[test]
    fn watcher_kind_and_persist_roundtrip() {
        with_temp(|path| {
            set_consent(true).unwrap();
            let item = create("watcher", "file change", "look at notes", 42).unwrap();
            assert_eq!(item.kind, AgencyKind::Watcher);
            // reload via fresh load
            drop(item);
            let store = {
                let raw = fs::read_to_string(&path).unwrap();
                serde_json::from_str::<AgencyFile>(&raw).unwrap()
            };
            assert!(store.consent);
            assert_eq!(store.items.len(), 1);
            assert_eq!(store.items[0].fire_at_ms, 42);
        });
    }
}
