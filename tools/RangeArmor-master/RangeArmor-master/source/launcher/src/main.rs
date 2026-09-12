use clap::{App, Arg, ArgMatches};
use json::JsonValue;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    let matches = App::new("RangeArmor Launcher")
        .version("1.5.0")
        .author("AnastacioEngine")
        .about("Launches a packaged AnastacioEngine game.")
        .arg(
            Arg::with_name("console")
                .short("c")
                .long("console")
                .help("Keep the console window visible"),
        )
        .arg(
            Arg::with_name("args")
                .short("a")
                .long("args")
                .takes_value(true)
                .multiple(true)
                .help("Pass one argument to RangeRuntime; repeat for more arguments"),
        )
        .arg(
            Arg::with_name("engine")
                .short("e")
                .long("engine")
                .takes_value(true)
                .help("Use a specific Engine<platform> config key"),
        )
        .arg(
            Arg::with_name("file")
                .short("f")
                .long("file")
                .takes_value(true)
                .help("Path to launcher/config.json or to the project directory"),
        )
        .get_matches();

    if !matches.is_present("console") {
        hide_console_window();
    }

    match launch(&matches) {
        Ok(status) if status.success() => {}
        Ok(status) => {
            eprintln!("X RangeRuntime exited with {status}");
            std::process::exit(status.code().unwrap_or(1));
        }
        Err(error) => {
            eprintln!("X {error}");
            std::process::exit(1);
        }
    }
}

fn hide_console_window() {
    #[cfg(target_os = "windows")]
    {
        use std::ptr;
        use winapi::um::wincon::GetConsoleWindow;
        use winapi::um::winuser::{ShowWindow, SW_HIDE};
        let window = unsafe { GetConsoleWindow() };
        if window != ptr::null_mut() {
            unsafe { ShowWindow(window, SW_HIDE) };
        }
    }
}

fn launch(matches: &ArgMatches) -> Result<std::process::ExitStatus, String> {
    let config_path = config_path(matches)?;
    let root = config_path
        .parent()
        .and_then(Path::parent)
        .ok_or_else(|| format!("Invalid config path: {}", config_path.display()))?;
    let config = read_config(&config_path)?;
    let engine_key = matches
        .value_of("engine")
        .map(|name| format!("Engine{name}"))
        .unwrap_or_else(default_engine_key);
    let engine_value = config[&engine_key]
        .as_str()
        .ok_or_else(|| format!("Could not find {engine_key} in {}", config_path.display()))?;
    let data_source = config["DataSource"]
        .as_str()
        .ok_or_else(|| "Could not find DataSource in launcher/config.json".to_owned())?;
    let main_file = config["MainFile"]
        .as_str()
        .ok_or_else(|| "Could not find MainFile in launcher/config.json".to_owned())?;

    let engine = root.join(engine_value);
    let data_dir = root.join(data_source);
    let game_file = data_dir.join(main_file);
    if !engine.is_file() {
        return Err(format!(
            "Could not find engine executable: {}",
            engine.display()
        ));
    }
    if !game_file.is_file() {
        return Err(format!("Could not find game file: {}", game_file.display()));
    }

    #[cfg(not(target_os = "windows"))]
    make_executable(&engine)?;

    let mut command = Command::new(&engine);
    command.current_dir(&data_dir);
    // RangeRuntime is not reliable when it receives a relative project path:
    // depending on its installation layout it can resolve it against the
    // launcher directory rather than `current_dir`. Pass the validated full
    // path so packaged games work independently of where they are extracted.
    command.arg(&game_file);
    if let Some(arguments) = matches.values_of("args") {
        command.args(arguments);
    }
    command
        .status()
        .map_err(|error| format!("Could not start {}: {error}", engine.display()))
}

fn config_path(matches: &ArgMatches) -> Result<PathBuf, String> {
    if let Some(path) = matches.value_of("file") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Ok(path);
        }
        let candidate = path.join("launcher/config.json");
        if candidate.is_file() {
            return Ok(candidate);
        }
        return Err(format!("Could not find config.json at {}", path.display()));
    }
    let executable =
        env::current_exe().map_err(|error| format!("Could not resolve launcher path: {error}"))?;
    let root = executable
        .parent()
        .ok_or_else(|| "Launcher has no parent directory".to_owned())?;
    Ok(root.join("launcher/config.json"))
}

fn read_config(path: &Path) -> Result<JsonValue, String> {
    let text = fs::read_to_string(path)
        .map_err(|error| format!("Could not read {}: {error}", path.display()))?;
    json::parse(&text).map_err(|error| format!("Could not parse {}: {error}", path.display()))
}

fn default_engine_key() -> String {
    if cfg!(target_os = "windows") {
        "EngineWindows64".to_owned()
    } else {
        "EngineLinux64".to_owned()
    }
}

#[cfg(not(target_os = "windows"))]
fn make_executable(path: &Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    let mut permissions = fs::metadata(path)
        .map_err(|error| format!("Could not inspect {}: {error}", path.display()))?
        .permissions();
    permissions.set_mode(permissions.mode() | 0o111);
    fs::set_permissions(path, permissions)
        .map_err(|error| format!("Could not make {} executable: {error}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_the_native_64_bit_engine_key() {
        assert_eq!(
            default_engine_key(),
            if cfg!(target_os = "windows") {
                "EngineWindows64"
            } else {
                "EngineLinux64"
            }
        );
    }

    #[test]
    fn parses_a_project_config() {
        let config = json::parse(r#"{"DataSource":"./data","MainFile":"game.rasec","EngineLinux64":"./engine/Linux64/RangeRuntime"}"#).unwrap();
        assert_eq!(config["DataSource"].as_str(), Some("./data"));
        assert_eq!(
            config["EngineLinux64"].as_str(),
            Some("./engine/Linux64/RangeRuntime")
        );
    }
}
