//! Scenario manifest read from `/arena/scenario.json` inside the container.

use serde::Deserialize;

/// Top-level scenario manifest.
#[derive(Debug, Deserialize)]
pub struct ScenarioManifest {
    pub title: String,
    pub prompt: ScenarioPrompt,
}

/// Incident prompt displayed to the user at the start of a challenge.
#[derive(Debug, Deserialize)]
pub struct ScenarioPrompt {
    pub title: String,
    pub body: String,
    #[serde(default)]
    pub environment: Option<String>,
    #[serde(default)]
    pub mission: Option<String>,
}

impl ScenarioManifest {
    /// Path to the scenario manifest inside the container.
    pub const MANIFEST_PATH: &str = "/arena/scenario.json";

    /// Formats the scenario prompt for terminal display with ANSI escape codes.
    pub fn format_prompt(&self) -> String {
        let mut out = String::new();
        out.push_str("\r\n");
        out.push_str(&format!("\x1b[1;31m{}\x1b[0m\r\n", self.prompt.title));
        out.push_str(&format!("\r\n{}\r\n", self.prompt.body));
        if let Some(ref env) = self.prompt.environment {
            out.push_str(&format!("\r\n\x1b[1mEnvironment:\x1b[0m {env}\r\n"));
        }
        if let Some(ref mission) = self.prompt.mission {
            out.push_str(&format!("\r\n\x1b[1mMission:\x1b[0m {mission}\r\n"));
        }
        out.push_str("\r\n");
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deserialize_full_manifest() {
        let json = r#"{
            "title": "The Cascade",
            "prompt": {
                "title": "INCIDENT ALERT - Priority: High",
                "body": "Checkout Success Rate dropped below 85%",
                "environment": "Kubernetes cluster prod-eu-west-1",
                "mission": "Identify the root cause"
            }
        }"#;
        let manifest: ScenarioManifest = serde_json::from_str(json).unwrap();
        assert_eq!(manifest.title, "The Cascade");
        assert_eq!(manifest.prompt.title, "INCIDENT ALERT - Priority: High");
        assert_eq!(
            manifest.prompt.body,
            "Checkout Success Rate dropped below 85%"
        );
        assert_eq!(
            manifest.prompt.environment.as_deref(),
            Some("Kubernetes cluster prod-eu-west-1")
        );
        assert_eq!(
            manifest.prompt.mission.as_deref(),
            Some("Identify the root cause")
        );
    }

    #[test]
    fn deserialize_minimal_manifest() {
        let json = r#"{
            "title": "Minimal",
            "prompt": {
                "title": "Alert",
                "body": "Something broke"
            }
        }"#;
        let manifest: ScenarioManifest = serde_json::from_str(json).unwrap();
        assert_eq!(manifest.title, "Minimal");
        assert!(manifest.prompt.environment.is_none());
        assert!(manifest.prompt.mission.is_none());
    }

    #[test]
    fn format_prompt_full() {
        let manifest = ScenarioManifest {
            title: "The Cascade".to_string(),
            prompt: ScenarioPrompt {
                title: "INCIDENT ALERT".to_string(),
                body: "Checkout rate dropped".to_string(),
                environment: Some("prod-eu-west-1".to_string()),
                mission: Some("Find root cause".to_string()),
            },
        };
        let output = manifest.format_prompt();
        assert!(output.contains("INCIDENT ALERT"));
        assert!(output.contains("Checkout rate dropped"));
        assert!(output.contains("prod-eu-west-1"));
        assert!(output.contains("Find root cause"));
    }

    #[test]
    fn format_prompt_minimal() {
        let manifest = ScenarioManifest {
            title: "Test".to_string(),
            prompt: ScenarioPrompt {
                title: "Alert".to_string(),
                body: "Broke".to_string(),
                environment: None,
                mission: None,
            },
        };
        let output = manifest.format_prompt();
        assert!(output.contains("Alert"));
        assert!(output.contains("Broke"));
        assert!(!output.contains("Environment"));
        assert!(!output.contains("Mission"));
    }
}
