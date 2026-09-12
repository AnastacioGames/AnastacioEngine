use crate::project::{self, LoadedProject};
use crate::runner::RunningTask;
use crate::theme;
use eframe::egui;
use std::path::{Path, PathBuf};

pub enum EditorAction {
    Close,
}

#[derive(Debug, PartialEq, Clone, Copy)]
enum Tab {
    Tasks,
    Project,
    Paths,
}

pub struct EditorState {
    tab: Tab,
    task: Option<RunningTask>,
    /// Transient message shown in the bottom status strip: why a gated
    /// button can't be used yet (set on click, not hover — see the
    /// `platform_gate`/`python_tooltip` call sites), or a save confirmation.
    status: Option<String>,
}

impl Default for EditorState {
    fn default() -> Self {
        Self {
            tab: Tab::Tasks,
            task: None,
            status: None,
        }
    }
}

pub fn show(
    ui: &mut egui::Ui,
    state: &mut EditorState,
    project: &mut LoadedProject,
    error: &mut Option<String>,
) -> Option<EditorAction> {
    let mut action = None;

    if let Some(task) = &mut state.task {
        task.poll();
        if task.is_running() {
            // Background threads deliver output asynchronously with no OS
            // input event attached, so without this the log would only
            // redraw whenever the mouse happens to move.
            ui.ctx().request_repaint();
        }
    }

    ui.horizontal(|ui| {
        ui.label(egui::RichText::new(&project.data.game_name).strong().size(16.0));
        ui.label(egui::RichText::new(format!("v{}", project.data.version)).small().color(theme::COLOR_MUTED));

        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            // Save is a manual re-confirmation more than a "there are unsaved
            // changes" action (every field edit already autosaves), so it
            // stays visually calm — the accent color is reserved for the
            // primary Tasks actions instead of being spent here too.
            if ui.button("💾  Save").clicked() {
                match project::save(project) {
                    Ok(()) => state.status = Some("Project saved".to_owned()),
                    Err(e) => *error = Some(format!("Could not save project:\n{e}")),
                }
            }
            if ui.button("📂  Explore").clicked() {
                open_in_file_manager(&project.dir);
            }
            if ui.button("⬅  Close Project").clicked() {
                action = Some(EditorAction::Close);
            }
        });
    });
    ui.add_space(4.0);

    ui.horizontal(|ui| {
        ui.selectable_value(&mut state.tab, Tab::Tasks, "Tasks");
        ui.selectable_value(&mut state.tab, Tab::Project, "Project");
        ui.selectable_value(&mut state.tab, Tab::Paths, "Paths");
    });
    ui.separator();
    ui.add_space(8.0);

    let changed = match state.tab {
        Tab::Tasks => tasks_tab(ui, project, &mut state.task, error, &mut state.status, &mut state.tab),
        Tab::Project => project_tab(ui, project, error),
        Tab::Paths => paths_tab(ui, project, error),
    };

    if changed {
        match project::save(project) {
            Ok(()) => state.status = Some("Project saved".to_owned()),
            Err(e) => *error = Some(format!("Could not save project:\n{e}")),
        }
    }

    show_task_window(ui.ctx(), &mut state.task);
    status_strip(ui, project, &state.status);

    action
}

/// Bottom status strip, always present: shows the last transient message
/// (a save confirmation, or why a gated Tasks button was refused) when one
/// is set, otherwise a standing summary of how many platforms are ready to
/// run/export — so the strip is never just dead space.
fn status_strip(ui: &mut egui::Ui, project: &LoadedProject, status: &Option<String>) {
    ui.add_space(10.0);
    ui.separator();
    ui.add_space(4.0);

    if let Some(message) = status {
        ui.label(egui::RichText::new(message).small().color(theme::COLOR_MUTED));
        return;
    }

    let python_valid = python_current_os(project).is_some();
    let data_valid = project.dir.join(&project.data.data_source).is_dir();
    let ready = project::DEFAULT_PLATFORMS
        .iter()
        .filter(|p| platform_gate(project, p, python_valid, data_valid).0)
        .count();
    ui.label(
        egui::RichText::new(format!(
            "{ready}/{} platform(s) ready to run or export",
            project::DEFAULT_PLATFORMS.len()
        ))
        .small()
        .color(theme::COLOR_MUTED),
    );
}

/// A script invocation resolved from `python_current_os` + `release_dir`,
/// surfacing any spawn failure through the shared error modal instead of
/// silently doing nothing.
fn spawn_task(
    project: &LoadedProject,
    error: &mut Option<String>,
    label: impl Into<String>,
    script_file: &str,
    extra_args: Vec<String>,
) -> Option<RunningTask> {
    let Some(python) = python_current_os(project) else {
        *error = Some("Python executable for current platform must be set first.".to_owned());
        return None;
    };
    let script = project::release_dir().join("scripts").join(script_file);
    match RunningTask::spawn(label, &python, &script, &project.config_path, &extra_args) {
        Ok(task) => Some(task),
        Err(e) => {
            *error = Some(format!("Could not start task:\n{e}"));
            None
        }
    }
}

/// Shows the active task's live log (or its final result) in a modal
/// window on top of every tab — mirrors the Godot original's
/// `AcceptDialog.popup_centered_ratio` covering the whole screen during
/// `_run_script`, except this one streams output live instead of appearing
/// only once the (previously blocking) call returns.
fn show_task_window(ctx: &egui::Context, task_slot: &mut Option<RunningTask>) {
    let Some(task) = task_slot else { return };
    let mut close = false;

    egui::Window::new(task.label.clone())
        .collapsible(false)
        .resizable(true)
        .anchor(egui::Align2::CENTER_CENTER, egui::Vec2::ZERO)
        .default_size([520.0, 360.0])
        .show(ctx, |ui| {
            match task.finished {
                None => {
                    ui.horizontal(|ui| {
                        ui.spinner();
                        if let Some(stage) = &task.stage {
                            ui.label(stage);
                        } else if task.progress > 0 {
                            ui.label(format!("{} files processed", task.progress));
                        } else {
                            ui.label("Running…");
                        }
                    });
                }
                Some(true) => {
                    ui.colored_label(theme::accent(), "✔ Task completed");
                }
                Some(false) => {
                    ui.colored_label(theme::COLOR_INVALID, "✘ Task failed or was cancelled");
                }
            }
            ui.add_space(6.0);

            egui::ScrollArea::vertical()
                .max_height(240.0)
                .stick_to_bottom(true)
                .show(ui, |ui| {
                    // Selectable so a user hitting an error can drag-select a
                    // line without needing the copy-all button below.
                    for line in &task.log {
                        ui.add(egui::Label::new(egui::RichText::new(line).monospace()).selectable(true));
                    }
                });

            ui.add_space(6.0);
            ui.horizontal(|ui| {
                if task.is_running() {
                    if ui.button("Cancel").clicked() {
                        task.cancel();
                    }
                } else if ui.button("Close").clicked() {
                    close = true;
                }
                // The scroll area is short and drag-selecting past its edge
                // doesn't auto-scroll, so copying everything at once is the
                // reliable way to grab a full error to paste elsewhere.
                if ui.button("📋  Copy Log").clicked() {
                    ctx.copy_text(task.log.join("\n"));
                }
            });
        });

    if close {
        *task_slot = None;
    }
}

/// Finds a Python interpreter to run RangeArmor's own release scripts with,
/// mirroring `editor.gd::_get_python_current_os`: prefer the Python bundled
/// with the running Range Engine install itself (two directories up from
/// this executable — `build/bin/` — via the project's `AlternativePython(Linux)`
/// suffix), falling back to the project's own per-platform `Python*` path.
fn python_current_os(project: &LoadedProject) -> Option<PathBuf> {
    if let Some(exe) = std::env::current_exe().ok() {
        if let Some(range_dir) = exe.parent().and_then(Path::parent) {
            let alt = range_dir.join(project.data.alternative_python.trim_start_matches('/'));
            if alt.is_file() {
                return Some(alt);
            }
            let alt_linux =
                range_dir.join(project.data.alternative_python_linux.trim_start_matches('/'));
            if alt_linux.is_file() {
                return Some(alt_linux);
            }
        }
    }

    let p64 = if cfg!(target_os = "windows") {
        &project.data.python_windows64
    } else {
        &project.data.python_linux64
    };
    let p64_path = project.dir.join(p64);
    if p64_path.is_file() {
        return Some(p64_path);
    }
    for candidate in if cfg!(target_os = "windows") { ["python", "py"] } else { ["python3", "python"] } {
        if std::process::Command::new(candidate).arg("--version").output().is_ok() {
            return Some(PathBuf::from(candidate));
        }
    }
    None
}

/// Per-platform runtime paths used by the Tasks tab's Run/Export gating.
/// The launcher starts RangeRuntime directly; a Python interpreter is only
/// required on the authoring machine for the packaging scripts.
fn platform_paths<'a>(data: &'a project::ProjectData, platform: &str) -> &'a str {
    match platform {
        "Windows64" => &data.engine_windows64,
        "Linux64" => &data.engine_linux64,
        _ => unreachable!("platform must be one of project::DEFAULT_PLATFORMS"),
    }
}

/// Mirrors `editor.gd::_update_task_buttons`: gate every button on whether a
/// Python interpreter was found at all, then further gate each platform's
/// Run/Export pair on that platform's own Engine+Python paths existing, and
/// on the data source folder existing. Read-only — unlike the original,
/// this doesn't save the project on every recompute, since here it runs
/// every frame rather than only on specific triggers.
fn tasks_tab(
    ui: &mut egui::Ui,
    project: &mut LoadedProject,
    task: &mut Option<RunningTask>,
    error: &mut Option<String>,
    status: &mut Option<String>,
    tab: &mut Tab,
) -> bool {
    let mut changed = false;
    let python_valid = python_current_os(project).is_some();
    let python_tooltip = "Python executable for current platform must be set first.";
    let data_valid = project.dir.join(&project.data.data_source).is_dir();
    // A task is already showing its own modal window; block starting a
    // second, overlapping one from underneath it. This is a real (transient)
    // disable, unlike the reason-based gates below, so it still uses
    // `add_enabled` — there's nothing useful to explain, it's obviously busy.
    let idle = task.is_none();

    theme::card().show(ui, |ui| {
        ui.set_min_width(ui.available_width());
        ui.label(egui::RichText::new("General tasks").strong());
        ui.add_space(6.0);
        ui.horizontal(|ui| {
            if ui.add_enabled(idle, egui::Button::new("🛠  Copy Available Range Engine Files")).clicked() {
                *task = spawn_task(
                    project,
                    error,
                    "Copy Range Engine Files",
                    "get_rangeengine_currentplatform.py",
                    vec!["--all-platforms".to_owned()],
                );
            }
            if gated_button(ui, idle, python_valid, python_tooltip, Some(Tab::Paths), tab, "🖼  Set Icons", status) {
                pick_icon(&project.dir, "Pick launcher icon (.ico)", "icons/icon-launcher.ico", error);
                pick_icon(&project.dir, "Pick engine icon (.ico)", "icons/icon-engine.ico", error);
                let resource_hacker = project::release_dir().join("tools").join("ResourceHacker.exe");
                *task = spawn_task(
                    project,
                    error,
                    "Set Icons",
                    "set_icons.py",
                    vec![
                        "--resource-hacker".to_owned(),
                        resource_hacker.to_string_lossy().into_owned(),
                    ],
                );
            }
        });
    });
    ui.add_space(14.0);

    ui.columns(2, |columns| {
        columns[0].vertical(|ui| {
            theme::card().show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.label(egui::RichText::new("Run game").strong());
                ui.add_space(6.0);
                for platform in project::DEFAULT_PLATFORMS {
                    let (enabled, reason, jump) = platform_gate(project, platform, python_valid, data_valid);
                    if gated_button(ui, idle, enabled, reason, jump, tab, platform, status) {
                        *task = spawn_task(
                            project,
                            error,
                            format!("Run {platform}"),
                            "run_launcher.py",
                            vec!["--engine".to_owned(), platform.to_owned()],
                        );
                    }
                }
            });
        });

        columns[1].vertical(|ui| {
            theme::card().show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.label(egui::RichText::new("Export to").strong());
                ui.add_space(6.0);
                for platform in project::DEFAULT_PLATFORMS {
                    let (enabled, reason, jump) = platform_gate(project, platform, python_valid, data_valid);
                    if gated_button(ui, idle, enabled, reason, jump, tab, platform, status) {
                        let mut args = vec!["--target".to_owned(), platform.to_owned()];
                        if project.data.export_compress {
                            args.push("--compress".to_owned());
                        }
                        *task = spawn_task(project, error, format!("Export {platform}"), "build_release.py", args);
                    }
                }
                ui.add_space(6.0);
                if gated_button(ui, idle, python_valid, python_tooltip, Some(Tab::Paths), tab, "All Platforms", status) {
                    let mut args = vec!["--target".to_owned(), "All".to_owned()];
                    if project.data.export_compress {
                        args.push("--compress".to_owned());
                    }
                    *task = spawn_task(project, error, "Export All Platforms", "build_release.py", args);
                }
                ui.add_space(6.0);
                if ui
                    .checkbox(&mut project.data.export_compress, "Compress targets after export")
                    .changed()
                {
                    changed = true;
                }
            });
        });
    });

    changed
}

/// A Tasks-tab action button that stays clickable even when its
/// prerequisites aren't met — clicking it while `!enabled` doesn't run the
/// task, it just writes `reason` into the shared status strip. This
/// replaces the earlier hover-tooltip approach: egui's disabled widgets
/// (`add_enabled(false, ...)`) never register hover at all, so a real
/// explanation needs a still-interactive widget. `idle` (no task already
/// running) is the one exception still enforced with a hard disable, since
/// "a task is already running" needs no further explanation.
/// Clicking a disabled button while its prerequisite lives on another tab
/// jumps straight there instead of leaving the user to remember which tab
/// that was — the round-trip between Tasks and Project/Paths was the main
/// complaint about this screen's flow.
fn gated_button(
    ui: &mut egui::Ui,
    idle: bool,
    enabled: bool,
    reason: &'static str,
    jump: Option<Tab>,
    tab: &mut Tab,
    label: &str,
    status: &mut Option<String>,
) -> bool {
    let text = if enabled {
        egui::RichText::new(label)
    } else {
        egui::RichText::new(label).color(theme::COLOR_MUTED)
    };
    let resp = ui.add_enabled(idle, egui::Button::new(text));
    if resp.clicked() {
        if enabled {
            return true;
        }
        *status = Some(reason.to_owned());
        if let Some(jump) = jump {
            *tab = jump;
        }
    }
    false
}

/// `(enabled, disabled_reason, tab_to_fix_it_on)` for one platform's
/// Run/Export button pair.
fn platform_gate(
    project: &LoadedProject,
    platform: &str,
    python_valid: bool,
    data_valid: bool,
) -> (bool, &'static str, Option<Tab>) {
    if !python_valid {
        return (
            false,
            "Python executable for current platform must be set first.",
            Some(Tab::Paths),
        );
    }
    if project.data.main_file == project::DEFAULT_MAIN_FILE {
        return (
            false,
            "Set the Main File in the Project tab to your own game — it's still the template placeholder.",
            Some(Tab::Project),
        );
    }
    let engine = platform_paths(&project.data, platform);
    let paths_valid = project.dir.join(engine).is_file();
    if !paths_valid {
        return (
            false,
            "The RangeRuntime executable must be set for this platform.",
            Some(Tab::Paths),
        );
    }
    if !data_valid {
        return (false, "Build the game data first to run or export.", Some(Tab::Project));
    }
    (true, "", None)
}

fn project_tab(ui: &mut egui::Ui, project: &mut LoadedProject, error: &mut Option<String>) -> bool {
    let mut changed = false;
    let dir = project.dir.clone();
    theme::card().show(ui, |ui| {
    ui.set_min_width(ui.available_width());
    ui.horizontal(|ui| {
        ui.add_sized([120.0, 22.0], egui::Label::new("Game Name"));
        changed |= ui.text_edit_singleline(&mut project.data.game_name).changed();
    });
    ui.horizontal(|ui| {
        ui.add_sized([120.0, 22.0], egui::Label::new("Version"));
        changed |= ui.text_edit_singleline(&mut project.data.version).changed();
    });

    changed |= path_field(
        ui,
        "Main File",
        &dir,
        &mut project.data.main_file,
        FieldKind::OpenFile {
            filter: Some(("RangeArmorSecurity File", "rasec")),
            filename_only: true,
        },
        true, // ignore_missing, same as NODE_FIELD_RELATIONS in editor.gd
        error,
    );
    changed |= path_field(
        ui,
        "Data Source",
        &dir,
        &mut project.data.data_source,
        FieldKind::PickFolder,
        false,
        error,
    );

    ui.add_space(4.0);
    changed |= ui
        .checkbox(&mut project.data.compile_scripts, "Compile Python scripts")
        .changed();
    });

    changed
}

fn paths_tab(ui: &mut egui::Ui, project: &mut LoadedProject, error: &mut Option<String>) -> bool {
    let mut changed = false;
    let dir = project.dir.clone();

    ui.columns(2, |columns| {
        columns[0].vertical(|ui| {
            theme::card().show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            ui.label(egui::RichText::new("Engine executables").strong());
            ui.add_space(6.0);
            changed |= path_field(
                ui,
                "Windows64",
                &dir,
                &mut project.data.engine_windows64,
                FieldKind::OpenFile {
                    filter: Some(("Executable", "exe")),
                    filename_only: false,
                },
                false,
                error,
            );
            changed |= path_field(
                ui,
                "Linux64",
                &dir,
                &mut project.data.engine_linux64,
                FieldKind::OpenFile {
                    filter: None,
                    filename_only: false,
                },
                false,
                error,
            );
            });
        });

        columns[1].vertical(|ui| {
            theme::card().show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            ui.label(egui::RichText::new("Python for authoring tools").strong());
            ui.add_space(6.0);
            changed |= path_field(
                ui,
                "Windows64",
                &dir,
                &mut project.data.python_windows64,
                FieldKind::OpenFile {
                    filter: Some(("Executable", "exe")),
                    filename_only: false,
                },
                false,
                error,
            );
            ui.label(egui::RichText::new("Not included in packaged games.").small().weak());
            changed |= path_field(
                ui,
                "Linux64",
                &dir,
                &mut project.data.python_linux64,
                FieldKind::OpenFile {
                    filter: None,
                    filename_only: false,
                },
                false,
                error,
            );
            });
        });
    });

    changed
}

enum FieldKind {
    OpenFile {
        filter: Option<(&'static str, &'static str)>,
        filename_only: bool,
    },
    PickFolder,
}

/// Renders a `Label` + path-value `Button` row. Clicking opens a native
/// picker; the picked path is stored relative to the project directory
/// (or, for `filename_only` fields like `MainFile`, just the file name) —
/// mirrors `editor.gd::_on_FileDialog_any_selected`. The button text is
/// colored red when the path doesn't resolve under the project (unless
/// `ignore_missing`), mirroring `editor.gd::_update_fields`'s
/// `COLOR_INVALID` handling.
fn path_field(
    ui: &mut egui::Ui,
    label: &str,
    project_dir: &Path,
    value: &mut String,
    kind: FieldKind,
    ignore_missing: bool,
    error: &mut Option<String>,
) -> bool {
    let mut changed = false;
    let exists = ignore_missing || project_dir.join(&value).exists();
    let color = if exists {
        theme::COLOR_VALID
    } else {
        theme::COLOR_INVALID
    };

    ui.horizontal(|ui| {
        ui.add_sized([120.0, 22.0], egui::Label::new(label));
        let icon = if exists { "✔" } else { "✘" };
        ui.label(egui::RichText::new(icon).color(color));
        let resp = ui.add_sized(
            [ui.available_width(), 22.0],
            egui::Button::new(egui::RichText::new(value.as_str()).color(color)),
        );
        if !exists {
            resp.clone().on_hover_text("Could not find this target.");
        }
        if resp.clicked() {
            let dialog = rfd::FileDialog::new().set_directory(project_dir);
            let picked = match &kind {
                FieldKind::PickFolder => dialog.pick_folder(),
                FieldKind::OpenFile { filter, .. } => {
                    let dialog = match filter {
                        Some((name, ext)) => dialog.add_filter(*name, &[*ext]),
                        None => dialog,
                    };
                    dialog.pick_file()
                }
            };
            if let Some(picked) = picked {
                let filename_only = matches!(kind, FieldKind::OpenFile { filename_only: true, .. });
                match relative_to_project(&picked, project_dir, filename_only) {
                    Some(rel) => {
                        *value = rel;
                        changed = true;
                    }
                    None => {
                        *error = Some("Path must be inside project folder!".to_owned());
                    }
                }
            }
        }
    });

    changed
}

/// `./sub/dir/file.ext` relative to `project_dir`, or just the file name
/// when `filename_only`. Returns `None` if `picked` isn't under
/// `project_dir` at all.
fn relative_to_project(picked: &Path, project_dir: &Path, filename_only: bool) -> Option<String> {
    if filename_only {
        return picked.file_name().map(|f| f.to_string_lossy().into_owned());
    }

    let picked_norm = crate::config::normalize(picked);
    let dir_norm = crate::config::normalize(project_dir);
    let rel = picked_norm.strip_prefix(&dir_norm)?.trim_start_matches('/');
    Some(format!("./{rel}"))
}

/// Opens a native file picker for an `.ico` file and copies it to
/// `dest_rel` inside the project, overwriting whatever `set_icons.py`
/// would otherwise apply unchanged. Cancelling the dialog leaves the
/// existing icon untouched. `set_icons.py` always reads from these two
/// fixed paths (`icons/icon-launcher.ico` / `icons/icon-engine.ico`), so
/// this is the only way to change which icon it applies without leaving
/// the app to replace the file manually.
fn pick_icon(project_dir: &Path, title: &str, dest_rel: &str, error: &mut Option<String>) {
    let picked = rfd::FileDialog::new()
        .set_title(title)
        .add_filter("Icon", &["ico"])
        .set_directory(project_dir)
        .pick_file();

    if let Some(picked) = picked {
        if let Err(e) = std::fs::copy(&picked, project_dir.join(dest_rel)) {
            *error = Some(format!("Could not copy icon:\n{e}"));
        }
    }
}

fn open_in_file_manager(dir: &PathBuf) {
    #[cfg(target_os = "windows")]
    let _ = std::process::Command::new("explorer").arg(dir).spawn();
    #[cfg(not(target_os = "windows"))]
    let _ = std::process::Command::new("xdg-open").arg(dir).spawn();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_path_keeps_subfolder_structure() {
        let rel = relative_to_project(
            Path::new(r"D:\RolimaRacer\projetoRR\engine\Windows64\RangeRuntime.exe"),
            Path::new(r"D:\RolimaRacer\projetoRR"),
            false,
        );
        assert_eq!(rel.as_deref(), Some("./engine/Windows64/RangeRuntime.exe"));
    }

    #[test]
    fn relative_path_works_across_mixed_separators() {
        // rfd returns native `\` on Windows; the stored project dir may have
        // been normalized to `/` already (or vice versa) — both must match.
        let rel = relative_to_project(
            Path::new(r"D:\RolimaRacer\projetoRR\data"),
            Path::new("D:/RolimaRacer/projetoRR"),
            false,
        );
        assert_eq!(rel.as_deref(), Some("./data"));
    }

    #[test]
    fn filename_only_ignores_subfolder() {
        let rel = relative_to_project(
            Path::new(r"D:\RolimaRacer\projetoRR\data\RolimaRacer.rasec"),
            Path::new(r"D:\RolimaRacer\projetoRR"),
            true,
        );
        assert_eq!(rel.as_deref(), Some("RolimaRacer.rasec"));
    }

    #[test]
    fn rejects_a_path_outside_the_project() {
        let rel = relative_to_project(
            Path::new(r"C:\Somewhere\Else\RangeRuntime.exe"),
            Path::new(r"D:\RolimaRacer\projetoRR"),
            false,
        );
        assert_eq!(rel, None);
    }

    struct TempDir(PathBuf);

    impl TempDir {
        fn new(name: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "rangearmor_editor_test_{name}_{}_{}",
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
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn platform_gate_requires_python_first() {
        let dir = TempDir::new("gate_python");
        let project = project::create(&dir.0, &project::release_dir()).unwrap();

        let (enabled, reason, jump) = platform_gate(&project, "Windows64", false, true);
        assert!(!enabled);
        assert!(reason.contains("Python executable"));
        assert_eq!(jump, Some(Tab::Paths));
    }

    #[test]
    fn platform_gate_requires_main_file_to_be_set() {
        let dir = TempDir::new("gate_main_file");
        let project = project::create(&dir.0, &project::release_dir()).unwrap();

        // A freshly scaffolded project still points MainFile at the
        // template placeholder until the user sets their own game.
        let (enabled, reason, jump) = platform_gate(&project, "Windows64", true, true);
        assert!(!enabled);
        assert!(reason.contains("Main File"));
        assert_eq!(jump, Some(Tab::Project));
    }

    #[test]
fn platform_gate_requires_engine_path_to_exist() {
        let dir = TempDir::new("gate_paths");
        let mut project = project::create(&dir.0, &project::release_dir()).unwrap();
        project.data.main_file = "MyGame.rasec".to_owned();

        // DEFAULT_FIELDS points at engine/python paths that don't exist yet
        // in a freshly scaffolded project, so the pair must be disabled.
        let (enabled, reason, jump) = platform_gate(&project, "Windows64", true, true);
        assert!(!enabled);
        assert!(reason.contains("must be set for this platform"));
        assert_eq!(jump, Some(Tab::Paths));
    }

    #[test]
    fn platform_gate_requires_data_source_once_paths_exist() {
        let dir = TempDir::new("gate_data");
        let mut project = project::create(&dir.0, &project::release_dir()).unwrap();
        project.data.main_file = "MyGame.rasec".to_owned();

        // Fake the engine/python executables into existence for this platform.
        std::fs::create_dir_all(dir.0.join("engine/Windows64")).unwrap();
        std::fs::write(dir.0.join("engine/Windows64/RangeRuntime.exe"), b"").unwrap();
        std::fs::create_dir_all(dir.0.join("engine/Windows64/2.79/python/bin")).unwrap();
        std::fs::write(
            dir.0.join("engine/Windows64/2.79/python/bin/python.exe"),
            b"",
        )
        .unwrap();
        project.data.engine_windows64 = "./engine/Windows64/RangeRuntime.exe".to_owned();
        project.data.python_windows64 = "./engine/Windows64/2.79/python/bin/python.exe".to_owned();

        let (enabled, reason, jump) = platform_gate(&project, "Windows64", true, false);
        assert!(!enabled);
        assert!(reason.contains("Build the game data first"));
        assert_eq!(jump, Some(Tab::Project));

        let (enabled, _, _) = platform_gate(&project, "Windows64", true, true);
        assert!(enabled);
    }
}
