use eframe::egui::{
    self, Color32, CornerRadius, FontData, FontDefinitions, FontFamily, FontId, Margin, Shadow,
    Stroke, TextStyle, Vec2,
};
use std::collections::BTreeMap;
use std::sync::Arc;

// Accent matches the RangeArmor shield/logo coral-red, giving the UI a real
// focal color instead of the near-monochrome gray of the Godot original.
const ACCENT: Color32 = Color32::from_rgb(0xE2, 0x57, 0x4C);
const ACCENT_HOVER: Color32 = Color32::from_rgb(0xEA, 0x6E, 0x64);
const ACCENT_ACTIVE: Color32 = Color32::from_rgb(0xC7, 0x45, 0x3B);

const BG_WINDOW: Color32 = Color32::from_rgb(0x14, 0x14, 0x16);
const BG_PANEL: Color32 = Color32::from_rgb(0x1B, 0x1B, 0x1E);
const BG_WIDGET: Color32 = Color32::from_rgb(0x23, 0x23, 0x27);
const BG_WIDGET_HOVER: Color32 = Color32::from_rgb(0x2C, 0x2C, 0x31);
const BG_WIDGET_ACTIVE: Color32 = Color32::from_rgb(0x30, 0x30, 0x36);
const BG_EXTREME: Color32 = Color32::from_rgb(0x0E, 0x0E, 0x10);

const TEXT_PRIMARY: Color32 = Color32::from_rgb(0xF2, 0xF1, 0xEF);
const TEXT_MUTED: Color32 = Color32::from_rgb(0x9A, 0x99, 0x9F);

pub const COLOR_VALID: Color32 = TEXT_PRIMARY;
pub const COLOR_INVALID: Color32 = Color32::from_rgb(0xFF, 0x78, 0x78);
pub const COLOR_MUTED: Color32 = TEXT_MUTED;

const CORNER: u8 = 8;

/// Slightly-raised background used for grouped-content cards, distinct
/// enough from `BG_PANEL` to read as a surface without competing with it.
const BG_CARD: Color32 = Color32::from_rgb(0x1F, 0x1F, 0x23);
const CARD_STROKE: Color32 = Color32::from_rgba_premultiplied(0xFF, 0xFF, 0xFF, 10);

/// Applies the RangeArmor Panel visual identity: dark theme, coral accent,
/// consistent rounded corners, and a real typographic hierarchy.
pub fn apply(ctx: &egui::Context) {
    ctx.set_theme(egui::Theme::Dark);
    load_fonts(ctx);

    let mut visuals = egui::Visuals::dark();
    visuals.override_text_color = Some(TEXT_PRIMARY);
    visuals.hyperlink_color = ACCENT_HOVER;
    visuals.panel_fill = BG_PANEL;
    visuals.window_fill = BG_WINDOW;
    visuals.window_stroke = Stroke::new(1.0, Color32::from_rgb(0x2A, 0x2A, 0x2E));
    visuals.window_corner_radius = CornerRadius::same(CORNER);
    visuals.menu_corner_radius = CornerRadius::same(CORNER);
    visuals.extreme_bg_color = BG_EXTREME;
    visuals.faint_bg_color = BG_WIDGET;
    visuals.error_fg_color = COLOR_INVALID;
    visuals.warn_fg_color = Color32::from_rgb(0xE8, 0xB8, 0x4C);
    visuals.selection.bg_fill = ACCENT.gamma_multiply(0.55);
    visuals.selection.stroke = Stroke::new(1.0, ACCENT);
    visuals.window_shadow = Shadow {
        offset: [0, 8],
        blur: 24,
        spread: 0,
        color: Color32::from_black_alpha(120),
    };

    // Resting state of interactive widgets (buttons, checkboxes, combo boxes).
    visuals.widgets.inactive.bg_fill = BG_WIDGET;
    visuals.widgets.inactive.weak_bg_fill = BG_WIDGET;
    visuals.widgets.inactive.bg_stroke = Stroke::new(1.0, Color32::from_rgb(0x2C, 0x2C, 0x31));
    visuals.widgets.inactive.fg_stroke = Stroke::new(1.0, TEXT_PRIMARY);
    visuals.widgets.inactive.corner_radius = CornerRadius::same(CORNER);

    // Hovered state must read clearly as "about to interact".
    visuals.widgets.hovered.bg_fill = BG_WIDGET_HOVER;
    visuals.widgets.hovered.weak_bg_fill = BG_WIDGET_HOVER;
    visuals.widgets.hovered.bg_stroke = Stroke::new(1.5, ACCENT_HOVER);
    visuals.widgets.hovered.fg_stroke = Stroke::new(1.0, TEXT_PRIMARY);
    visuals.widgets.hovered.corner_radius = CornerRadius::same(CORNER);
    visuals.widgets.hovered.expansion = 1.0;

    // Active/pressed state.
    visuals.widgets.active.bg_fill = BG_WIDGET_ACTIVE;
    visuals.widgets.active.weak_bg_fill = BG_WIDGET_ACTIVE;
    visuals.widgets.active.bg_stroke = Stroke::new(1.5, ACCENT_ACTIVE);
    visuals.widgets.active.fg_stroke = Stroke::new(1.0, TEXT_PRIMARY);
    visuals.widgets.active.corner_radius = CornerRadius::same(CORNER);

    // Non-interactive frames (group boxes, separators, plain panels).
    visuals.widgets.noninteractive.bg_fill = BG_PANEL;
    visuals.widgets.noninteractive.bg_stroke = Stroke::new(1.0, Color32::from_rgba_premultiplied(0xFF, 0xFF, 0xFF, 14));
    visuals.widgets.noninteractive.fg_stroke = Stroke::new(1.0, TEXT_MUTED);
    visuals.widgets.noninteractive.corner_radius = CornerRadius::same(CORNER);

    visuals.widgets.open.bg_fill = BG_WIDGET_ACTIVE;
    visuals.widgets.open.weak_bg_fill = BG_WIDGET_ACTIVE;
    visuals.widgets.open.bg_stroke = Stroke::new(1.5, ACCENT);
    visuals.widgets.open.corner_radius = CornerRadius::same(CORNER);

    ctx.set_visuals(visuals);

    ctx.all_styles_mut(|style| {
        style.spacing.item_spacing = Vec2::new(10.0, 10.0);
        style.spacing.button_padding = Vec2::new(14.0, 8.0);
        style.spacing.window_margin = Margin::same(16);
        style.spacing.menu_margin = Margin::same(10);
        style.spacing.interact_size.y = 30.0;

        let mut text_styles = BTreeMap::new();
        text_styles.insert(TextStyle::Heading, FontId::new(24.0, FontFamily::Proportional));
        text_styles.insert(TextStyle::Body, FontId::new(14.0, FontFamily::Proportional));
        text_styles.insert(TextStyle::Button, FontId::new(14.5, FontFamily::Proportional));
        text_styles.insert(TextStyle::Small, FontId::new(11.5, FontFamily::Proportional));
        text_styles.insert(TextStyle::Monospace, FontId::new(13.0, FontFamily::Monospace));
        style.text_styles = text_styles;
    });
}

fn load_fonts(ctx: &egui::Context) {
    let mut fonts = FontDefinitions::default();
    fonts.font_data.insert(
        "roboto_medium".to_owned(),
        Arc::new(FontData::from_static(include_bytes!(
            "../../../roboto_medium.ttf"
        ))),
    );
    fonts
        .families
        .entry(FontFamily::Proportional)
        .or_default()
        .insert(0, "roboto_medium".to_owned());
    ctx.set_fonts(fonts);
}

/// Accent color for primary call-to-action buttons (New Project, Export, etc).
pub fn accent() -> Color32 {
    ACCENT
}

/// Frame for a discrete content card (recent-project row, grouped fields):
/// a subtly raised surface with a hairline border, distinct from bare panel
/// background without competing with real widgets.
pub fn card() -> egui::Frame {
    egui::Frame::new()
        .fill(BG_CARD)
        .stroke(Stroke::new(1.0, CARD_STROKE))
        .corner_radius(CornerRadius::same(CORNER))
        .inner_margin(Margin::same(12))
}
