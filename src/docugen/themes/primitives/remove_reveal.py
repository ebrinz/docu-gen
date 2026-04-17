"""remove_reveal — DEPRECATED. Use llm_custom for new projects."""

NAME = "remove_reveal"
DESCRIPTION = "DEPRECATED: one compound fades, another emerges. Use llm_custom."
CUE_EVENTS = {"remove", "reveal"}
AUDIO_SPANS = [
    {"trigger": "remove", "offset": 0.0, "duration": 1.0,
     "audio": "fade_down", "curve": "ramp_down"},
    {"trigger": "reveal", "offset": 0.0, "duration": 0.8,
     "audio": "rise", "curve": "ramp_up"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {"removed": "", "emerged": ""}
NEEDS_CONTENT = False
DEPRECATED = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Ported verbatim from biopunk._choreo_remove_reveal.
    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    params = {}
    for cue in cue_words:
        params.update(cue.get("params", {}))
    removed = params.get("removed", "A")
    emerged = params.get("emerged", "B")
    via = params.get("via", "C")
    effect = params.get("effect", "")
    beat = min(duration * 0.12, 2.0)
    effect_code = ""
    if effect:
        effect_code = f'''
        eff = Text("{effect}", font="Courier", color=GOLD, weight=BOLD).scale(0.6)
        eff.next_to(via_text, DOWN, buff=0.3)
        self.play(FadeIn(eff, scale=1.3), run_time=0.8)
        throb_title(self, eff, cycles=1, scale_factor=1.05)'''
    return f'''        # Remove-reveal: {removed} -> {emerged}
        dot1 = Dot(LEFT * 2, radius=0.2, color=GOLD).set_opacity(0.9)
        dot1_label = Text("{removed}", font="Courier", color=GOLD, weight=BOLD).scale(0.4)
        dot1_label.next_to(dot1, DOWN, buff=0.2)
        self.play(FadeIn(dot1, scale=2.0), FadeIn(dot1_label), run_time=1.0)
        alive_wait(self, {beat:.1f}, particles=bg)
        cross = Cross(stroke_color=SITH_RED, stroke_width=6).scale(0.3).move_to(dot1)
        removed_text = Text("REMOVED", font="Courier", color=SITH_RED, weight=BOLD).scale(0.4)
        removed_text.next_to(dot1, UP, buff=0.4)
        self.play(Create(cross), dot1.animate.set_opacity(0.15), FadeIn(removed_text, scale=1.3), run_time=0.8)
        alive_wait(self, {beat:.1f}, particles=bg)
        self.play(FadeOut(cross), FadeOut(removed_text), FadeOut(dot1), FadeOut(dot1_label), run_time=0.5)
        alive_wait(self, {beat:.1f}, particles=bg)
        dot2 = Dot(RIGHT * 2, radius=0.2, color=GLOW).set_opacity(0.9)
        dot2_label = Text("{emerged}", font="Courier", color=GLOW, weight=BOLD).scale(0.45)
        dot2_label.next_to(dot2, DOWN, buff=0.2)
        self.play(FadeIn(dot2, scale=3.0), FadeIn(dot2_label), run_time=1.0)
        via_text = Text("via {via}", font="Courier", color=PURPLE).scale(0.3)
        via_text.next_to(dot2_label, DOWN, buff=0.15)
        self.play(FadeIn(via_text), run_time=0.5){effect_code}
        alive_wait(self, {max(duration - 9.0, 1.0):.1f}, particles=bg)'''
