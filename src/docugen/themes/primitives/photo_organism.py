"""photo_organism — photo inset with HUD pointer labels. Migrated from biopunk."""

NAME = "photo_organism"
DESCRIPTION = "Photo inset with HUD border, animated pointer labels"
CUE_EVENTS = {"show_photo", "show_structure", "show_name", "show_note"}
AUDIO_SPANS = [
    {"trigger": "show_photo", "offset": 0.0, "duration": 1.2,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "show_name", "offset": 0.0, "duration": 0.8,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "show_structure", "offset": 0.0, "duration": 0.8,
     "audio": "trace_hum", "curve": "sustain"},
    {"trigger": "show_note", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = True
DEPRECATED = False

_palette = {
    "bg": "#050510", "panel": "#0a0e1a", "glow": "#b8ffc4", "glow_dim": "#4a7a52",
    "purple": "#8b5cf6", "purple_deep": "#5b21b6", "purple_faint": "#3b1a6e",
    "sith_red": "#dc2626", "sith_red_dim": "#7f1d1d", "cyan": "#22d3ee",
    "gold": "#f59e0b", "text": "#e2e8f0", "text_dim": "#64748b", "grid": "#1a1a2e",
}


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    word_times = clip.get("word_times", [])
    label_code_parts = []
    label_count = 0
    for cue in cue_words:
        event = cue.get("event", "")
        params = cue.get("params", {})
        idx = cue.get("at_index", 0)
        t = word_times[idx]["start"] if idx < len(word_times) else 0
        if event in ("show_name", "show_note", "show_structure"):
            text = params.get("name", params.get("note", params.get("structure", "")))
            color = {"show_name": _palette["gold"], "show_note": _palette["cyan"],
                     "show_structure": _palette["purple"]}[event]
            i = label_count
            label_code_parts.append(f'''
        # Cue: {event} at {t:.2f}s
        current_time_{i} = self.renderer.time if hasattr(self.renderer, 'time') else 0
        wait_{i} = max(0, {t:.2f} - current_time_{i})
        if wait_{i} > 0:
            self.wait(wait_{i})
        lbl_{i} = Text("{text}", color="{color}", font_size=22)
        lbl_box_{i} = SurroundingRectangle(lbl_{i}, color="{color}",
                                            fill_color="{_palette['bg']}", fill_opacity=0.85,
                                            buff=0.15, corner_radius=0.05)
        lbl_group_{i} = VGroup(lbl_box_{i}, lbl_{i})
        frame = self.layers.get('content', {{}}).get('asset_0', None)
        if frame:
            lbl_group_{i}.next_to(frame, RIGHT, buff=0.8).shift(DOWN * {i * 0.9 - 0.5})
            pointer_{i} = Line(
                frame.get_right() + RIGHT * 0.1,
                lbl_group_{i}.get_left() + LEFT * 0.1,
                color="{color}", stroke_width=1.5,
            )
            self.play(Create(pointer_{i}), FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        else:
            lbl_group_{i}.move_to(RIGHT * 2 + DOWN * {i * 0.9 - 0.5})
            self.play(FadeIn(lbl_group_{i}, shift=RIGHT * 0.2), run_time=0.8)
        self.wait(0.3)''')
            label_count += 1
    labels_block = "\n".join(label_code_parts)
    hold = max(duration - 2.0 - label_count * 1.1, 0.5)
    return f'''        # Organism reveal with cue-synced labels
{labels_block}
        alive_wait(self, {hold:.1f}, particles=bg)'''
