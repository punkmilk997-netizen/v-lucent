//! P6 privacy helpers - redact secrets from logs (API keys, tokens, gateway).

/// Redact common secret patterns from a log line or error string.
pub fn redact_secrets(input: &str) -> String {
    let mut out = input.to_string();
    out = redact_header_values(&out);
    out = redact_json_fields(&out);
    out = redact_prefixed_keys(&out);
    out = redact_env_assignments(&out);
    out
}

/// Print a line after redaction (use instead of println! for dynamic content).
pub fn safe_log(line: impl AsRef<str>) {
    println!("{}", redact_secrets(line.as_ref()));
}

fn redact_header_values(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let lower = s.to_ascii_lowercase();
    let mut i = 0;
    while i < s.len() {
        let rest_l = &lower[i..];
        let mut matched = false;
        for prefix in [
            "authorization: bearer ",
            "authorization: token ",
            "authorization: ",
            "bearer ",
            "token ",
        ] {
            if rest_l.starts_with(prefix) {
                out.push_str(&s[i..i + prefix.len()]);
                i += prefix.len();
                let (_secret, consumed) = take_secret_token(&s[i..]);
                if consumed > 0 {
                    out.push_str("[REDACTED]");
                    i += consumed;
                }
                matched = true;
                break;
            }
        }
        if matched {
            continue;
        }
        let ch = s[i..].chars().next().unwrap();
        out.push(ch);
        i += ch.len_utf8();
    }
    out
}

fn take_secret_token(s: &str) -> (String, usize) {
    let mut end = 0usize;
    for (idx, c) in s.char_indices() {
        if c.is_whitespace() || matches!(c, '"' | '\'' | ',' | '}' | ';' | ')') {
            end = idx;
            break;
        }
        end = idx + c.len_utf8();
    }
    if end == 0 {
        return (String::new(), 0);
    }
    (s[..end].to_string(), end)
}

fn redact_json_fields(s: &str) -> String {
    let keys = [
        "api_key",
        "apiKey",
        "openrouter_api_key",
        "groq_api_key",
        "vision_api_key",
        "tts_api_key",
        "stt_api_key",
        "gateway_token",
        "GATEWAY_TOKEN",
        "access_token",
    ];
    let mut out = s.to_string();
    for key in keys {
        let needle = format!("\"{}\"", key);
        let mut result = String::new();
        let mut rest = out.as_str();
        while let Some(idx) = rest.find(&needle) {
            result.push_str(&rest[..idx]);
            result.push_str(&needle);
            let after_key = &rest[idx + needle.len()..];
            let trimmed = after_key.trim_start();
            let ws = after_key.len() - trimmed.len();
            result.push_str(&after_key[..ws]);
            if let Some(stripped) = trimmed.strip_prefix(':') {
                let trimmed2 = stripped.trim_start();
                let ws2 = stripped.len() - trimmed2.len();
                result.push(':');
                result.push_str(&stripped[..ws2]);
                if let Some(stripped3) = trimmed2.strip_prefix('"') {
                    result.push('"');
                    let end = stripped3.find('"').unwrap_or(stripped3.len());
                    result.push_str("[REDACTED]");
                    result.push('"');
                    rest = &stripped3[end..];
                    if rest.starts_with('"') {
                        rest = &rest[1..];
                    }
                    continue;
                }
            }
            rest = after_key;
        }
        result.push_str(rest);
        out = result;
    }
    out
}

fn redact_prefixed_keys(s: &str) -> String {
    let prefixes = ["sk-", "sk_", "gsk_", "xai-"];
    let mut out = String::with_capacity(s.len());
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0usize;
    while i < chars.len() {
        let mut hit = None;
        for p in prefixes {
            let pchars: Vec<char> = p.chars().collect();
            if i + pchars.len() <= chars.len() && chars[i..i + pchars.len()] == pchars[..] {
                if i > 0 {
                    let prev = chars[i - 1];
                    if prev.is_ascii_alphanumeric() || prev == '_' || prev == '-' {
                        continue;
                    }
                }
                hit = Some(pchars.len());
                break;
            }
        }
        if let Some(plen) = hit {
            for c in chars.iter().skip(i).take(plen) {
                out.push(*c);
            }
            i += plen;
            let start = i;
            while i < chars.len() {
                let c = chars[i];
                if c.is_ascii_alphanumeric() || c == '_' || c == '-' {
                    i += 1;
                } else {
                    break;
                }
            }
            if i > start {
                out.push_str("[REDACTED]");
            }
            continue;
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

fn redact_env_assignments(s: &str) -> String {
    let keys = [
        "GATEWAY_TOKEN",
        "OPENCLAW_TOKEN",
        "VISION_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPGRAM_API_KEY",
        "ELEVENLABS_API_KEY",
        "OPENAI_API_KEY",
    ];
    let mut out = s.to_string();
    for key in keys {
        for sep in ['=', ':'] {
            let needle = format!("{}{}", key, sep);
            let mut result = String::new();
            let mut rest = out.as_str();
            while let Some(idx) = find_ci(rest, &needle) {
                result.push_str(&rest[..idx]);
                result.push_str(&rest[idx..idx + needle.len()]);
                let after = &rest[idx + needle.len()..];
                let trimmed = after.trim_start();
                let ws = after.len() - trimmed.len();
                result.push_str(&after[..ws]);
                let (_secret, consumed) = take_secret_token(trimmed);
                if consumed == 0 {
                    rest = trimmed;
                } else {
                    result.push_str("[REDACTED]");
                    rest = &trimmed[consumed..];
                }
            }
            result.push_str(rest);
            out = result;
        }
    }
    out
}

fn find_ci(hay: &str, needle: &str) -> Option<usize> {
    hay.to_ascii_lowercase()
        .find(&needle.to_ascii_lowercase())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_bearer_and_sk() {
        let s = "Authorization: Bearer sk-abcDEF1234567890 and more";
        let r = redact_secrets(s);
        assert!(r.contains("[REDACTED]"), "{}", r);
        assert!(!r.contains("sk-abcDEF1234567890"), "{}", r);
    }

    #[test]
    fn redacts_json_api_key() {
        let s = r#"{"groq_api_key":"gsk_live_secret_value_here","model":"x"}"#;
        let r = redact_secrets(s);
        assert!(r.contains("[REDACTED]"), "{}", r);
        assert!(!r.contains("gsk_live_secret_value_here"), "{}", r);
    }

    #[test]
    fn redacts_gateway_env() {
        let s = "GATEWAY_TOKEN=super-secret-gateway-token-xyz";
        let r = redact_secrets(s);
        assert!(r.contains("[REDACTED]"), "{}", r);
        assert!(!r.contains("super-secret-gateway-token-xyz"), "{}", r);
    }

    #[test]
    fn keeps_benign_text() {
        let s = "[Groq] Response status: 200 (42 ms)";
        assert_eq!(redact_secrets(s), s);
    }
}