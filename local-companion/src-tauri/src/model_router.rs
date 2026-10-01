//! Explicit light / heavy / vision model routing (P4).
//! gpt-oss (or any) models are selected only from settings strings — never hardcoded here.

use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum RouterTier {
    Light,
    Heavy,
    Vision,
}

impl RouterTier {
    pub fn as_str(self) -> &'static str {
        match self {
            RouterTier::Light => "light",
            RouterTier::Heavy => "heavy",
            RouterTier::Vision => "vision",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RouterDecision {
    pub tier: RouterTier,
    pub model: String,
    pub reason: String,
}

impl RouterDecision {
    pub fn log_line(&self, context: &str) {
        println!(
            "[Router] {} tier={} model={} reason={}",
            context,
            self.tier.as_str(),
            self.model,
            self.reason
        );
    }
}

/// Heuristic: long or code/planning-ish user text -> heavy path when router is on.
pub fn message_looks_complex(text: &str) -> bool {
    let lower = text.to_lowercase();
    let len = text.chars().count();
    if len > 220 {
        return true;
    }
    const KEYS: &[&str] = &[
        "plan",
        "fix",
        "debug",
        "refactor",
        "implement",
        "architecture",
        "stack trace",
        "compile",
        "cargo ",
        "typescript",
        "python",
        "rustc",
        "```",
        "function ",
        "class ",
        "error:",
        "traceback",
        "step by step",
        "compare",
        "analyze",
        "write a",
        "build a",
        "design a",
    ];
    KEYS.iter().any(|k| lower.contains(k))
}

fn trim_nonempty(s: &str) -> Option<String> {
    let t = s.trim();
    if t.is_empty() {
        None
    } else {
        Some(t.to_string())
    }
}

/// Resolve chat model: light (`groq_model`) vs heavy (`heavy_model`).
/// `requested` from the client is only used as the light base when it matches settings
/// or when the router is off; never invents gpt-oss unless settings provide it.
pub fn resolve_chat(
    model_router: bool,
    light_model: &str,
    heavy_model: &str,
    user_text: &str,
    tools_path: bool,
    requested: Option<&str>,
) -> RouterDecision {
    let light = trim_nonempty(light_model)
        .or_else(|| requested.and_then(trim_nonempty))
        .unwrap_or_default();
    let heavy = trim_nonempty(heavy_model).unwrap_or_default();

    if !model_router || heavy.is_empty() {
        let reason = if !model_router {
            "router_off"
        } else {
            "heavy_unset"
        };
        return RouterDecision {
            tier: RouterTier::Light,
            model: light,
            reason: reason.to_string(),
        };
    }

    let complex = message_looks_complex(user_text);
    if tools_path {
        return RouterDecision {
            tier: RouterTier::Heavy,
            model: heavy,
            reason: "tools_path".to_string(),
        };
    }
    if complex {
        return RouterDecision {
            tier: RouterTier::Heavy,
            model: heavy,
            reason: "complex_message".to_string(),
        };
    }
    RouterDecision {
        tier: RouterTier::Light,
        model: light,
        reason: "simple_chat".to_string(),
    }
}

/// Vision turns always use `vision_model` when set; otherwise fall back to light settings model.
pub fn resolve_vision(vision_model: &str, light_fallback: &str) -> RouterDecision {
    if let Some(m) = trim_nonempty(vision_model) {
        return RouterDecision {
            tier: RouterTier::Vision,
            model: m,
            reason: "vision_model_setting".to_string(),
        };
    }
    if let Some(m) = trim_nonempty(light_fallback) {
        return RouterDecision {
            tier: RouterTier::Vision,
            model: m,
            reason: "vision_fallback_light".to_string(),
        };
    }
    RouterDecision {
        tier: RouterTier::Vision,
        model: String::new(),
        reason: "vision_model_missing".to_string(),
    }
}

/// After a tool call, upgrade light -> heavy when router is enabled and heavy is configured.
pub fn upgrade_after_tool(
    current: &RouterDecision,
    model_router: bool,
    heavy_model: &str,
) -> RouterDecision {
    let heavy = match trim_nonempty(heavy_model) {
        Some(h) if model_router => h,
        _ => return current.clone(),
    };
    if current.tier == RouterTier::Heavy && current.model == heavy {
        return current.clone();
    }
    RouterDecision {
        tier: RouterTier::Heavy,
        model: heavy,
        reason: "tool_call_upgrade".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIGHT: &str = "openai/gpt-oss-20b";
    const HEAVY: &str = "openai/gpt-oss-120b";
    const VISION: &str = "qwen/qwen3.8-27b";

    #[test]
    fn light_simple_chat() {
        let d = resolve_chat(true, LIGHT, HEAVY, "hey what's up?", false, None);
        assert_eq!(d.tier, RouterTier::Light);
        assert_eq!(d.model, LIGHT);
        assert_eq!(d.reason, "simple_chat");
    }

    #[test]
    fn heavy_on_complex_keywords() {
        let d = resolve_chat(
            true,
            LIGHT,
            HEAVY,
            "please debug this rustc error and refactor",
            false,
            None,
        );
        assert_eq!(d.tier, RouterTier::Heavy);
        assert_eq!(d.model, HEAVY);
        assert_eq!(d.reason, "complex_message");
    }

    #[test]
    fn heavy_on_long_message() {
        let long = "a".repeat(221);
        let d = resolve_chat(true, LIGHT, HEAVY, &long, false, None);
        assert_eq!(d.tier, RouterTier::Heavy);
        assert_eq!(d.model, HEAVY);
    }

    #[test]
    fn heavy_on_tools_path() {
        let d = resolve_chat(true, LIGHT, HEAVY, "hi", true, None);
        assert_eq!(d.tier, RouterTier::Heavy);
        assert_eq!(d.reason, "tools_path");
    }

    #[test]
    fn router_off_stays_light_even_if_complex() {
        let d = resolve_chat(
            false,
            LIGHT,
            HEAVY,
            "implement architecture and debug",
            true,
            None,
        );
        assert_eq!(d.tier, RouterTier::Light);
        assert_eq!(d.model, LIGHT);
        assert_eq!(d.reason, "router_off");
    }

    #[test]
    fn heavy_unset_never_invents_gpt_oss_120b() {
        let d = resolve_chat(
            true,
            "my-custom-light",
            "",
            "implement and debug please",
            true,
            None,
        );
        assert_eq!(d.tier, RouterTier::Light);
        assert_eq!(d.model, "my-custom-light");
        assert_eq!(d.reason, "heavy_unset");
        assert!(!d.model.contains("120b"));
    }

    #[test]
    fn gpt_oss_only_from_settings_not_hardcoded_when_custom() {
        let d = resolve_chat(
            true,
            "vendor/other-8b",
            "vendor/other-70b",
            "hi",
            false,
            Some("openai/gpt-oss-20b"), // client hint ignored while router picks from settings light
        );
        assert_eq!(d.model, "vendor/other-8b");
        assert!(!d.model.contains("gpt-oss"));
    }

    #[test]
    fn vision_uses_vision_setting() {
        let d = resolve_vision(VISION, LIGHT);
        assert_eq!(d.tier, RouterTier::Vision);
        assert_eq!(d.model, VISION);
        assert_eq!(d.reason, "vision_model_setting");
    }

    #[test]
    fn vision_fallback_to_light_not_hardcoded_gpt_oss() {
        let d = resolve_vision("", "acme/vision-lite");
        assert_eq!(d.model, "acme/vision-lite");
        assert_eq!(d.reason, "vision_fallback_light");
    }

    #[test]
    fn tool_upgrade_from_light() {
        let start = resolve_chat(true, LIGHT, HEAVY, "hi", false, None);
        let up = upgrade_after_tool(&start, true, HEAVY);
        assert_eq!(up.tier, RouterTier::Heavy);
        assert_eq!(up.model, HEAVY);
        assert_eq!(up.reason, "tool_call_upgrade");
    }

    #[test]
    fn tool_upgrade_noop_when_router_off() {
        let start = resolve_chat(false, LIGHT, HEAVY, "hi", false, None);
        let up = upgrade_after_tool(&start, false, HEAVY);
        assert_eq!(up.tier, RouterTier::Light);
        assert_eq!(up.model, LIGHT);
    }
}
