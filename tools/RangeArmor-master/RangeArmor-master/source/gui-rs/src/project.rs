use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

/// The running app's own version stamp, compared against a project's
/// `BGArmorVersion` to decide whether its bundled runtime files need
/// updating. Version 116 replaces the legacy Python launcher with the native
/// `Launcher` executable, so existing projects must be refreshed once.
pub const APP_VERSION: i64 = 116;

/// Resolves the `release/` folder that ships template project files (icons,
/// the example `.rasec` and `Launcher(.exe)`). In production
/// this sits next to the compiled binary (`build/bin/rangearmor/release/`);
/// under `cargo run` it falls back to RangeArmor's own source-tree
/// `release/` folder, mirroring the two-path fallback in
/// `welcome.gd::_get_pathfile` (adapted for a real binary layout instead of
/// Godot's `res://` export quirk).
pub fn release_dir() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            let candidate = exe_dir.join("release");
            if candidate.is_dir() {
                return candidate;
            }
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../release")
}

/// Platforms RangeArmor can target, in menu order. Mirrors
/// `globals.gd::DEFAULT_PLATFORMS`.
pub const DEFAULT_PLATFORMS: [&str; 2] = ["Windows64", "Linux64"];

/// `ProjectData::main_file`'s default value: the template `.rasec` copied
/// into every new project. `MainFile`'s existence is never validated (its
/// `path_field` call in the Project tab passes `ignore_missing = true`,
/// mirroring `editor.gd`'s `NODE_FIELD_RELATIONS`), so a project left on
/// this placeholder never turns red on its own — the Run/Export gate checks
/// against this constant instead to catch a game whose Main File was never
/// pointed at the real project.
pub const DEFAULT_MAIN_FILE: &str = "Example Game.rasec";

/// Folder skeleton created for a brand new project. Mirrors
/// `globals.gd::DEFAULT_PROJECT_FOLDERS`.
pub const DEFAULT_PROJECT_FOLDERS: [&str; 7] = [
    "",
    "data",
    "engine",
    "engine/Linux64",
    "engine/Windows64",
    "launcher",
    "icons",
];

/// Template files copied into a brand new project, relative to both the
/// RangeArmor release folder (source) and the new project dir (destination).
/// Mirrors `globals.gd::DEFAULT_PROJECT_FILES`.
pub const DEFAULT_PROJECT_FILES: [&str; 5] = [
    "data/Example Game.rasec",
    "icons/icon-engine.ico",
    "icons/icon-launcher.ico",
    "launcher/Launcher.exe",
    "launcher/Launcher",
];

/// A game project's `launcher/config.json`. Field names, JSON keys and
/// defaults mirror `globals.gd::DEFAULT_FIELDS` exactly, so projects created
/// or edited by the Godot version of RangeArmor Panel keep working here.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectData {
    #[serde(rename = "GameName")]
    pub game_name: String,
    #[serde(rename = "Version")]
    pub version: String,
    #[serde(rename = "BGArmorVersion")]
    pub bg_armor_version: i64,
    #[serde(rename = "MainFile")]
    pub main_file: String,
    #[serde(rename = "DataFile")]
    pub data_file: String,
    #[serde(rename = "DataSource")]
    pub data_source: String,
    #[serde(rename = "DataChunkSize")]
    pub data_chunk_size: i64,
    #[serde(rename = "CompressionLevel")]
    pub compression_level: i64,
    #[serde(rename = "CompileScripts")]
    pub compile_scripts: bool,
    #[serde(rename = "ExportCompress")]
    pub export_compress: bool,
    #[serde(rename = "EngineWindows32")]
    pub engine_windows32: String,
    #[serde(rename = "EngineWindows64")]
    pub engine_windows64: String,
    #[serde(rename = "EngineLinux32")]
    pub engine_linux32: String,
    #[serde(rename = "EngineLinux64")]
    pub engine_linux64: String,
    #[serde(rename = "PythonWindows32")]
    pub python_windows32: String,
    #[serde(rename = "PythonWindows64")]
    pub python_windows64: String,
    #[serde(rename = "PythonLinux32")]
    pub python_linux32: String,
    #[serde(rename = "PythonLinux64")]
    pub python_linux64: String,
    #[serde(rename = "AlternativePython")]
    pub alternative_python: String,
    #[serde(rename = "AlternativePythonLinux")]
    pub alternative_python_linux: String,
    #[serde(rename = "Persistent")]
    pub persistent: Vec<String>,
    #[serde(rename = "Ignore")]
    pub ignore: Vec<String>,
}

impl Default for ProjectData {
    fn default() -> Self {
        Self {
            game_name: "Game".to_owned(),
            version: "1.0.0".to_owned(),
            bg_armor_version: 0,
            main_file: DEFAULT_MAIN_FILE.to_owned(),
            data_file: "./data.dat".to_owned(),
            data_source: "./data".to_owned(),
            data_chunk_size: 32,
            compression_level: 1,
            compile_scripts: false,
            export_compress: false,
            engine_windows32: "./engine/Windows32/RangeRuntime.exe".to_owned(),
            engine_windows64: "./engine/Windows64/RangeRuntime.exe".to_owned(),
            engine_linux32: "./engine/Linux32/RangeRuntime".to_owned(),
            engine_linux64: "./engine/Linux64/RangeRuntime".to_owned(),
            python_windows32: "./engine/Windows32/2.79/python/bin/python.exe".to_owned(),
            python_windows64: "./engine/Windows64/2.79/python/bin/python.exe".to_owned(),
            python_linux32: "./engine/Linux32/2.79/python/bin/python3.5m".to_owned(),
            python_linux64: "./engine/Linux64/2.79/python/bin/python3.11".to_owned(),
            alternative_python: "/2.79/python/bin/python.exe".to_owned(),
            alternative_python_linux: "/2.79/python/bin/python3.11".to_owned(),
            persistent: vec!["*.bgeconf".to_owned()],
            ignore: vec!["*.pyc".to_owned(), "*.range".to_owned()],
        }
    }
}

/// The exact set of JSON keys `ProjectData` accepts, used to reject unknown
/// fields exactly like `welcome.gd::_validate_data`'s first loop does.
fn known_field_names() -> HashSet<&'static str> {
    [
        "GameName",
        "Version",
        "BGArmorVersion",
        "MainFile",
        "DataFile",
        "DataSource",
        "DataChunkSize",
        "CompressionLevel",
        "CompileScripts",
        "ExportCompress",
        "EngineWindows32",
        "EngineWindows64",
        "EngineLinux32",
        "EngineLinux64",
        "PythonWindows32",
        "PythonWindows64",
        "PythonLinux32",
        "PythonLinux64",
        "AlternativePython",
        "AlternativePythonLinux",
        "Persistent",
        "Ignore",
    ]
    .into_iter()
    .collect()
}

#[derive(Debug)]
pub enum ValidationError {
    /// The JSON root wasn't an object at all.
    NotAnObject,
    /// The project file contains a key `ProjectData` doesn't know about.
    UnknownField(String),
    /// A known field had the wrong JSON type (e.g. a string where a number
    /// was expected).
    Malformed(String),
}

/// Validates a project's raw JSON exactly like `welcome.gd::_validate_data`:
/// reject any unrecognized top-level key, then fill in defaults for any
/// missing one before deserializing into `ProjectData`.
pub fn validate_and_upgrade(raw: serde_json::Value) -> Result<ProjectData, ValidationError> {
    let serde_json::Value::Object(mut map) = raw else {
        return Err(ValidationError::NotAnObject);
    };

    let known = known_field_names();
    for key in map.keys() {
        if !known.contains(key.as_str()) {
            return Err(ValidationError::UnknownField(key.clone()));
        }
    }

    let defaults = serde_json::to_value(ProjectData::default())
        .expect("ProjectData::default() always serializes");
    let serde_json::Value::Object(default_map) = defaults else {
        unreachable!("ProjectData serializes to a JSON object");
    };
    for (key, value) in default_map {
        map.entry(key).or_insert(value);
    }

    serde_json::from_value(serde_json::Value::Object(map))
        .map_err(|e| ValidationError::Malformed(e.to_string()))
}

/// Mirrors `welcome.gd::_project_updated`: a project is up to date once its
/// stamped `BGArmorVersion` is at least the running app's version.
pub fn is_up_to_date(project: &ProjectData, app_version: i64) -> bool {
    project.bg_armor_version != 0 && project.bg_armor_version >= app_version
}

/// A project opened (or just created) in the editor: its directory, the
/// resolved path to `launcher/config.json`, and the parsed data.
#[derive(Debug, Clone)]
pub struct LoadedProject {
    pub dir: PathBuf,
    pub config_path: PathBuf,
    pub data: ProjectData,
}

#[derive(Debug)]
pub enum LoadError {
    Io(std::io::Error),
    Json(serde_json::Error),
    Validation(ValidationError),
}

#[derive(Debug)]
pub enum CreateError {
    AlreadyExists,
    Io(std::io::Error),
}

/// Strips `//`-prefixed comment lines before parsing, exactly like
/// `globals.gd::get_json_no_comments` (JSON has no comment syntax, but old
/// hand-edited project files sometimes have them).
fn strip_json_comments(text: &str) -> String {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.starts_with("//"))
        .collect::<Vec<_>>()
        .join("")
}

/// Loads and validates `<dir>/launcher/config.json`. Mirrors
/// `welcome.gd::_load_project`'s read+parse+validate steps (the recent-list
/// and screen-transition side effects stay in the UI layer).
pub fn load(dir: &Path) -> Result<LoadedProject, LoadError> {
    let config_path = dir.join("launcher").join("config.json");
    let text = fs::read_to_string(&config_path).map_err(LoadError::Io)?;
    let raw: serde_json::Value =
        serde_json::from_str(&strip_json_comments(&text)).map_err(LoadError::Json)?;
    let data = validate_and_upgrade(raw).map_err(LoadError::Validation)?;
    Ok(LoadedProject {
        dir: dir.to_path_buf(),
        config_path,
        data,
    })
}

/// Writes `launcher/config.json` back to disk. Mirrors
/// `globals.gd::save_project`.
pub fn save(project: &LoadedProject) -> std::io::Result<()> {
    let text = serde_json::to_string(&project.data).expect("ProjectData always serializes");
    fs::write(&project.config_path, text)
}

/// Scaffolds a brand new project at `dir`: creates `DEFAULT_PROJECT_FOLDERS`,
/// copies `DEFAULT_PROJECT_FILES` in from `release_dir`, writes a default
/// `launcher/config.json`, then loads it back. Mirrors
/// `welcome.gd::_create_new_project`.
pub fn create(dir: &Path, release_dir: &Path) -> Result<LoadedProject, CreateError> {
    if dir.is_dir() {
        return Err(CreateError::AlreadyExists);
    }

    for folder in DEFAULT_PROJECT_FOLDERS {
        fs::create_dir_all(dir.join(folder)).map_err(CreateError::Io)?;
    }

    for file in DEFAULT_PROJECT_FILES {
        let src = release_dir.join(file);
        let dst = dir.join(file);
        // Optional platform-specific binaries (e.g. the Linux `Launcher` on
        // Windows) may not exist in `release_dir`; skip those rather than
        // failing the whole scaffold, matching the tolerant `_error` handling
        // in the original GDScript.
        if src.is_file() {
            fs::copy(&src, &dst).map_err(CreateError::Io)?;
        }
    }

    let config_path = dir.join("launcher").join("config.json");
    let text = serde_json::to_string(&ProjectData::default()).expect("always serializes");
    fs::write(&config_path, text).map_err(CreateError::Io)?;

    load(dir).map_err(|e| match e {
        LoadError::Io(e) => CreateError::Io(e),
        LoadError::Json(_) | LoadError::Validation(_) => {
            unreachable!("just wrote a valid default ProjectData")
        }
    })
}

/// Copies platform `Launcher` executables when the project predates the
/// running app version from
/// `release_dir` into the project. Mirrors `welcome.gd::_update_runtime_files`.
pub fn update_runtime_files(project: &mut LoadedProject, release_dir: &Path) -> std::io::Result<()> {
    if !is_up_to_date(&project.data, APP_VERSION) {
        for file in ["launcher/Launcher.exe", "launcher/Launcher"] {
            let src = release_dir.join(file);
            if src.is_file() {
                fs::copy(&src, project.dir.join(file))?;
            }
        }
        project.data.bg_armor_version = APP_VERSION;
        save(project)?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A real `launcher/config.json` produced by the Godot version of
    /// RangeArmor Panel, byte-for-byte.
    const REAL_PROJECT_JSON: &str = r#"{"GameName":"Carrinho de Rolimã","Version":"2.0.0","BGArmorVersion":115,"MainFile":"RolimaRacer.rasec","DataFile":"./data.dat","DataSource":"./data","DataChunkSize":32,"CompressionLevel":1,"CompileScripts":true,"ExportCompress":false,"EngineWindows32":"./engine/Windows32/RangeRuntime.exe","EngineWindows64":"./engine/Windows64/RangeRuntime.exe","EngineLinux32":"./engine/Linux32/RangeRuntime","EngineLinux64":"./engine/Linux64/RangeRuntime","PythonWindows32":"./engine/Windows32/2.79/python/bin/python.exe","PythonWindows64":"./engine/Windows64/2.79/python/bin/python.exe","PythonLinux32":"./engine/Linux32/2.79/python/bin/python3.5m","PythonLinux64":"./engine/Linux64/2.79/python/bin/python3.10","AlternativePython":"/2.79/python/bin/python.exe","AlternativePythonLinux":"/2.79/python/bin/python3.10","Persistent":["*.bgeconf"],"Ignore":["*.pyc","*.range"]}"#;

    #[test]
    fn loads_real_project_from_godot_version() {
        let raw: serde_json::Value = serde_json::from_str(REAL_PROJECT_JSON).unwrap();
        let project = validate_and_upgrade(raw).expect("real project must validate");
        assert_eq!(project.game_name, "Carrinho de Rolimã");
        assert_eq!(project.bg_armor_version, 115);
        assert_eq!(project.main_file, "RolimaRacer.rasec");
        assert!(project.compile_scripts);
        assert_eq!(project.persistent, vec!["*.bgeconf"]);
    }

    #[test]
    fn round_trips_back_to_the_same_json_shape() {
        let raw: serde_json::Value = serde_json::from_str(REAL_PROJECT_JSON).unwrap();
        let project = validate_and_upgrade(raw.clone()).unwrap();
        let rewritten = serde_json::to_value(&project).unwrap();
        assert_eq!(raw, rewritten);
    }

    #[test]
    fn fills_in_missing_fields_with_defaults() {
        let raw = serde_json::json!({ "GameName": "Only Name Set" });
        let project = validate_and_upgrade(raw).expect("partial project must validate");
        assert_eq!(project.game_name, "Only Name Set");
        assert_eq!(project.version, ProjectData::default().version);
        assert_eq!(project.data_chunk_size, 32);
    }

    #[test]
    fn rejects_unknown_fields() {
        let raw = serde_json::json!({ "TotallyMadeUpField": true });
        match validate_and_upgrade(raw) {
            Err(ValidationError::UnknownField(field)) => assert_eq!(field, "TotallyMadeUpField"),
            other => panic!("expected UnknownField, got {other:?}"),
        }
    }

    #[test]
    fn version_zero_is_never_up_to_date() {
        let project = ProjectData::default();
        assert!(!is_up_to_date(&project, 0));
        assert!(!is_up_to_date(&project, 1));
    }

    #[test]
    fn version_upgrade_threshold() {
        let mut project = ProjectData::default();
        project.bg_armor_version = 10;
        assert!(is_up_to_date(&project, 10));
        assert!(is_up_to_date(&project, 5));
        assert!(!is_up_to_date(&project, 11));
    }

    /// A scratch directory under the OS temp folder, removed on drop, so
    /// filesystem tests don't leave junk behind or collide with each other.
    struct TempDir(PathBuf);

    impl TempDir {
        fn new(name: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "rangearmor_test_{name}_{}_{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            Self(dir)
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn creates_scaffolds_and_reloads_a_new_project() {
        let project_dir = TempDir::new("create");
        let release = release_dir();

        let created = create(&project_dir.0, &release).expect("create must succeed");
        assert_eq!(created.data, ProjectData::default());
        for folder in DEFAULT_PROJECT_FOLDERS {
            assert!(project_dir.0.join(folder).is_dir(), "missing folder {folder}");
        }

        let reloaded = load(&project_dir.0).expect("just-created project must load back");
        assert_eq!(reloaded.data, ProjectData::default());
    }

    #[test]
    fn create_refuses_to_overwrite_an_existing_directory() {
        let project_dir = TempDir::new("create_conflict");
        fs::create_dir_all(&project_dir.0).unwrap();

        match create(&project_dir.0, &release_dir()) {
            Err(CreateError::AlreadyExists) => {}
            other => panic!("expected AlreadyExists, got {other:?}"),
        }
    }

    #[test]
    fn save_persists_edits_and_load_reads_them_back() {
        let project_dir = TempDir::new("save_roundtrip");
        let mut project = create(&project_dir.0, &release_dir()).unwrap();

        project.data.game_name = "Renamed Game".to_owned();
        save(&project).expect("save must succeed");

        let reloaded = load(&project_dir.0).unwrap();
        assert_eq!(reloaded.data.game_name, "Renamed Game");
    }

    #[test]
    fn update_runtime_files_stamps_outdated_projects_to_app_version() {
        let project_dir = TempDir::new("upgrade");
        let mut project = create(&project_dir.0, &release_dir()).unwrap();
        project.data.bg_armor_version = 1; // older than APP_VERSION
        save(&project).unwrap();

        update_runtime_files(&mut project, &release_dir()).expect("must succeed");

        assert_eq!(project.data.bg_armor_version, APP_VERSION);
        let reloaded = load(&project_dir.0).unwrap();
        assert_eq!(reloaded.data.bg_armor_version, APP_VERSION);
    }

    #[test]
    fn update_runtime_files_leaves_up_to_date_projects_untouched() {
        let project_dir = TempDir::new("already_current");
        let mut project = create(&project_dir.0, &release_dir()).unwrap();
        project.data.bg_armor_version = APP_VERSION;
        save(&project).unwrap();

        update_runtime_files(&mut project, &release_dir()).expect("must succeed");

        assert_eq!(project.data.bg_armor_version, APP_VERSION);
    }
}
