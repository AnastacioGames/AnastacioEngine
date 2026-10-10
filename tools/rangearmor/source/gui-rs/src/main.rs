mod config;
mod project;
mod runner;
mod screens;
mod theme;

use config::AppConfig;
use eframe::egui;
use project::LoadedProject;
use screens::editor::{EditorAction, EditorState};
use screens::welcome::WelcomeAction;
use std::path::{Path, PathBuf};

enum Screen {
    Welcome,
    Editor(LoadedProject, EditorState),
}

struct RangeArmorApp {
    config: AppConfig,
    screen: Screen,
    error: Option<String>,
}

impl RangeArmorApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        egui_extras::install_image_loaders(&cc.egui_ctx);
        theme::apply(&cc.egui_ctx);
        Self {
            config: AppConfig::load(),
            screen: Screen::Welcome,
            error: None,
        }
    }

    /// Shared tail of both "New Project" and "Open Project": bring runtime
    /// files up to date, remember it in Recent, and switch to the editor.
    /// Mirrors the shared half of `welcome.gd::_load_project`.
    fn activate_project(&mut self, mut loaded: LoadedProject) {
        if let Err(e) = project::update_runtime_files(&mut loaded, &project::release_dir()) {
            self.error = Some(format!("Could not update runtime files:\n{e}"));
        }

        let dir_str = config::normalize(&loaded.dir);
        self.config.last_dir = dir_str.clone();
        self.config.add_recent(&dir_str);
        self.config.save();

        self.screen = Screen::Editor(loaded, EditorState::default());
    }

    fn try_open_project(&mut self, dir: &Path) {
        match project::load(dir) {
            Ok(loaded) => self.activate_project(loaded),
            Err(project::LoadError::Io(_)) => {
                self.error = Some(format!(
                    "Could not read file:\n{}",
                    dir.join("launcher/config.json").display()
                ));
            }
            Err(project::LoadError::Json(_)) | Err(project::LoadError::Validation(_)) => {
                self.error = Some(format!("Invalid project directory:\n{}", dir.display()));
            }
        }
    }

    fn try_create_project(&mut self, dir: &Path) {
        match project::create(dir, &project::release_dir()) {
            Ok(loaded) => self.activate_project(loaded),
            Err(project::CreateError::AlreadyExists) => {
                self.error = Some(format!(
                    "A folder with the same name already exists:\n{}",
                    dir.display()
                ));
            }
            Err(project::CreateError::Io(e)) => {
                self.error = Some(format!("Could not create project at:\n{}\n\n{e}", dir.display()));
            }
        }
    }

    fn show_error_modal(&mut self, ctx: &egui::Context) {
        let Some(message) = self.error.clone() else {
            return;
        };
        let mut open = true;
        egui::Window::new("Alerta!")
            .collapsible(false)
            .resizable(false)
            .anchor(egui::Align2::CENTER_CENTER, egui::Vec2::ZERO)
            .open(&mut open)
            .show(ctx, |ui| {
                ui.label(message);
                ui.add_space(8.0);
                if ui.button("OK").clicked() {
                    self.error = None;
                }
            });
        if !open {
            self.error = None;
        }
    }
}

impl eframe::App for RangeArmorApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let mut pending_open: Option<PathBuf> = None;
        let mut pending_new: Option<PathBuf> = None;
        let mut pending_close = false;

        egui::CentralPanel::default().show(ui, |ui| {
            // Faint brand backdrop behind every screen, dim enough to never
            // fight with foreground text or the Editor's dense forms.
            egui::Image::new(egui::include_image!("../../../textures/back_ground.png"))
                .tint(egui::Color32::from_white_alpha(22))
                .paint_at(ui, ui.max_rect());

            match &mut self.screen {
            Screen::Welcome => {
                if let Some(action) = screens::welcome::show(ui, &mut self.config) {
                    match action {
                        WelcomeAction::Open(dir) => pending_open = Some(dir),
                        WelcomeAction::New(dir) => pending_new = Some(dir),
                    }
                }
            }
            Screen::Editor(project, state) => {
                if let Some(EditorAction::Close) =
                    screens::editor::show(ui, state, project, &mut self.error)
                {
                    pending_close = true;
                }
            }
            }
        });

        // Applied outside the CentralPanel closure so these can freely take
        // `&mut self` without fighting the partial borrow of `self.screen`
        // held while that closure runs.
        if let Some(dir) = pending_open {
            self.try_open_project(&dir);
        }
        if let Some(dir) = pending_new {
            self.try_create_project(&dir);
        }
        if pending_close {
            self.screen = Screen::Welcome;
        }

        self.show_error_modal(ui.ctx());
    }
}

fn main() -> eframe::Result<()> {
    let icon = eframe::icon_data::from_png_bytes(include_bytes!("../../../icon.png"))
        .expect("failed to decode embedded icon.png");

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("RangeArmor Panel")
            .with_inner_size([900.0, 620.0])
            .with_min_inner_size([700.0, 480.0])
            .with_icon(icon),
        ..Default::default()
    };

    eframe::run_native(
        "RangeArmor Panel",
        options,
        Box::new(|cc| Ok(Box::new(RangeArmorApp::new(cc)))),
    )
}
