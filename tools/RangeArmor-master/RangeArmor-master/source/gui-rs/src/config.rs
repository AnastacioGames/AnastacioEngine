use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

const MAX_RECENT_PROJECTS: usize = 5;

/// Renders a path using forward slashes, regardless of platform.
///
/// Godot always stored `LastDir`/`RecentPaths` with `/` (its internal path
/// convention on every OS). `rfd`'s native Windows dialogs return paths with
/// `\`, so without this a project opened via "Open Project" and the same
/// project opened via its Recent-list entry would stringify differently and
/// show up as two separate entries instead of deduping to one.
pub fn normalize(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

/// Global app config (window-independent): last used directory and recent
/// project list. Mirrors `globals.gd`'s `DEFAULT_CONFIG` / `config` dict
/// exactly, field-for-field, so a config.json written by the Godot version
/// of RangeArmor Panel loads here unchanged.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(rename = "LastDir", default)]
    pub last_dir: String,
    #[serde(rename = "RecentPaths", default)]
    pub recent_paths: Vec<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            last_dir: String::new(),
            recent_paths: Vec::new(),
        }
    }
}

impl AppConfig {
    /// Same path Godot's `OS.get_user_data_dir()` resolved to for this app
    /// (`project.godot` sets `config/custom_user_dir_name="RangeArmor"`),
    /// so switching binaries keeps the user's recent-project list intact.
    pub fn path() -> Option<PathBuf> {
        let base_dirs = directories::BaseDirs::new()?;
        Some(base_dirs.data_dir().join("RangeArmor").join("config.json"))
    }

    pub fn load() -> Self {
        let Some(path) = Self::path() else {
            return Self::default();
        };
        let Ok(text) = std::fs::read_to_string(&path) else {
            return Self::default();
        };
        serde_json::from_str(&text).unwrap_or_default()
    }

    pub fn save(&self) {
        let Some(path) = Self::path() else { return };
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(text) = serde_json::to_string(self) {
            let _ = std::fs::write(path, text);
        }
    }

    /// Mirrors `globals.gd::add_project_to_recent`: move-to-front, dedupe,
    /// cap at `MAX_RECENT_PROJECTS`.
    pub fn add_recent(&mut self, path: &str) {
        self.recent_paths.retain(|p| p != path);
        self.recent_paths.insert(0, path.to_owned());
        self.recent_paths.truncate(MAX_RECENT_PROJECTS);
    }

    pub fn clear_recent(&mut self) {
        self.recent_paths.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_real_godot_config() {
        let json = r#"{"LastDir":"D:/RolimaRacer/projetoRR","RecentPaths":["D:/RolimaRacer/projetoRR","D:/ProjetoRolimaRacer"]}"#;
        let config: AppConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.last_dir, "D:/RolimaRacer/projetoRR");
        assert_eq!(config.recent_paths.len(), 2);
    }

    #[test]
    fn normalize_converts_backslashes_to_forward_slashes() {
        assert_eq!(
            normalize(Path::new(r"D:\RolimaRacer\projetoRR")),
            "D:/RolimaRacer/projetoRR"
        );
        assert_eq!(
            normalize(Path::new("D:/RolimaRacer/projetoRR")),
            "D:/RolimaRacer/projetoRR"
        );
    }

    #[test]
    fn add_recent_moves_existing_to_front_and_caps_at_five() {
        let mut config = AppConfig::default();
        for i in 0..6 {
            config.add_recent(&format!("path{i}"));
        }
        assert_eq!(config.recent_paths.len(), MAX_RECENT_PROJECTS);
        assert_eq!(config.recent_paths[0], "path5");

        config.add_recent("path3");
        assert_eq!(config.recent_paths[0], "path3");
        assert_eq!(config.recent_paths.len(), MAX_RECENT_PROJECTS);
    }
}
