use crate::config::AppConfig;
use crate::theme;
use eframe::egui;
use std::path::PathBuf;
use std::time::SystemTime;

/// What the user asked to do from the Welcome screen. The caller (the app's
/// top-level `update`) applies it, since opening/creating a project needs
/// mutable access to more than `show` borrows here (recent list *and*
/// screen state at once).
pub enum WelcomeAction {
    Open(PathBuf),
    New(PathBuf),
}

const API_DOCS_URL: &str =
    "https://rangeengine.tech/api/14/html/manual/tutorials/range_armor/index.html";
const SOURCE_URL: &str = "https://github.com/rangeengine/RangeArmor";

pub fn show(ui: &mut egui::Ui, config: &mut AppConfig) -> Option<WelcomeAction> {
    let mut action = None;

    ui.add_space(14.0);
    theme::card().show(ui, |ui| {
        ui.set_min_width(ui.available_width());
        ui.horizontal(|ui| {
            ui.add(
                egui::Image::new(egui::include_image!(
                    "../../../../textures/rangearmor_logo_name.png"
                ))
                .max_height(64.0)
                .maintain_aspect_ratio(true),
            );
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.add_space(4.0);
                ui.label(
                    egui::RichText::new(format!("v{}", crate::project::APP_VERSION))
                        .small()
                        .color(theme::COLOR_MUTED),
                );
                ui.separator();
                ui.label(
                    egui::RichText::new("Game packaging & release tool")
                        .color(theme::COLOR_MUTED),
                );
            });
        });
    });
    ui.add_space(16.0);

    ui.columns(2, |columns| {
        columns[0].vertical(|ui| {
            theme::card().show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.label(egui::RichText::new("Start").strong());
                ui.add_space(10.0);

                // Primary action: opening an existing project is the far
                // more common path once a user has one, so it gets the
                // accent color and the taller button.
                let open_btn = egui::Button::new(
                    egui::RichText::new("📂  Open Project").size(15.0).strong(),
                )
                .fill(theme::accent());
                if ui.add_sized([ui.available_width(), 48.0], open_btn).clicked() {
                    if let Some(path) = rfd::FileDialog::new()
                        .set_title("Open Project")
                        .set_directory(start_dir(config))
                        .pick_folder()
                    {
                        action = Some(WelcomeAction::Open(path));
                    }
                }
                ui.add_space(8.0);
                if ui
                    .add_sized(
                        [ui.available_width(), 36.0],
                        egui::Button::new("➕  New Project"),
                    )
                    .clicked()
                {
                    if let Some(path) = rfd::FileDialog::new()
                        .set_title("Create Project")
                        .set_directory(start_dir(config))
                        .save_file()
                    {
                        action = Some(WelcomeAction::New(path));
                    }
                }
            });

            ui.add_space(14.0);
            theme::card().show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.label(egui::RichText::new("Resources").strong());
                ui.add_space(8.0);
                if ui.link("📚  API Documentation").clicked() {
                    ui.ctx().open_url(egui::OpenUrl::same_tab(API_DOCS_URL));
                }
                ui.add_space(4.0);
                if ui.link("🔖  Source Code").clicked() {
                    ui.ctx().open_url(egui::OpenUrl::same_tab(SOURCE_URL));
                }
            });
        });

        columns[1].vertical(|ui| {
            let available_height = ui.available_height();
            theme::card().show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.set_min_height(available_height - 24.0);
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("Recent projects").strong());
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if !config.recent_paths.is_empty() && ui.small_button("Clear").clicked() {
                            config.clear_recent();
                            config.save();
                        }
                    });
                });
                ui.add_space(8.0);

                if config.recent_paths.is_empty() {
                    ui.weak("No recent projects yet — open or create one to see it here.");
                    return;
                }

                for path in config.recent_paths.clone() {
                    ui.add_space(4.0);
                    if recent_card(ui, &path).clicked() {
                        action = Some(WelcomeAction::Open(PathBuf::from(&path)));
                    }
                }
            });
        });
    });

    action
}

/// One clickable card in the Recent list: project folder name as the
/// primary label, full path underneath in muted text, and the config
/// file's last-modified date on the right — read straight from the
/// filesystem rather than tracked separately, so it stays accurate even
/// for projects edited outside this app.
fn recent_card(ui: &mut egui::Ui, path: &str) -> egui::Response {
    let name = PathBuf::from(path)
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| path.to_owned());
    let last_opened = last_modified_label(path);

    let frame = egui::Frame::new()
        .fill(ui.visuals().widgets.inactive.bg_fill)
        .stroke(ui.visuals().widgets.inactive.bg_stroke)
        .corner_radius(ui.visuals().widgets.inactive.corner_radius)
        .inner_margin(egui::Margin::symmetric(10, 8));

    let response = frame
        .show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new(name).strong());
                    ui.label(egui::RichText::new(path).small().color(theme::COLOR_MUTED));
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if let Some(label) = last_opened {
                        ui.label(egui::RichText::new(label).small().color(theme::COLOR_MUTED));
                    }
                });
            });
        })
        .response;

    let sense_area = ui.interact(
        response.rect,
        response.id.with("recent_card_click"),
        egui::Sense::click(),
    );
    if sense_area.hovered() {
        ui.painter().rect_stroke(
            response.rect,
            ui.visuals().widgets.inactive.corner_radius,
            egui::Stroke::new(1.5, theme::accent()),
            egui::StrokeKind::Inside,
        );
    }
    sense_area
}

/// Human-friendly "last opened" label from `<path>/launcher/config.json`'s
/// mtime, e.g. "2 days ago". Returns `None` if the file can't be stat'd
/// (project moved/deleted since it was added to Recent).
fn last_modified_label(path: &str) -> Option<String> {
    let config_path = PathBuf::from(path).join("launcher").join("config.json");
    let modified = std::fs::metadata(&config_path).ok()?.modified().ok()?;
    let elapsed = SystemTime::now().duration_since(modified).ok()?;
    let secs = elapsed.as_secs();

    Some(if secs < 3600 {
        "just now".to_owned()
    } else if secs < 86_400 {
        format!("{}h ago", secs / 3600)
    } else if secs < 86_400 * 30 {
        format!("{}d ago", secs / 86_400)
    } else {
        format!("{}mo ago", secs / (86_400 * 30))
    })
}

fn start_dir(config: &AppConfig) -> PathBuf {
    let last = PathBuf::from(&config.last_dir);
    if !config.last_dir.is_empty() && last.is_dir() {
        return last;
    }
    directories::UserDirs::new()
        .map(|dirs| dirs.home_dir().to_path_buf())
        .unwrap_or_default()
}
