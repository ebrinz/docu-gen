"""dot_merge — DEPRECATED. Parse-evol chemistry-specific; use llm_custom for
new projects. Kept here so older clips.json files still render."""

NAME = "dot_merge"
DESCRIPTION = "DEPRECATED: two compound dots approach and merge. Use llm_custom."
CUE_EVENTS = {"show_dot1", "show_dot2", "merge"}
AUDIO_SPANS = [
    {"trigger": "show_dot1", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "show_dot2", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
    {"trigger": "merge", "offset": -1.5, "duration": 1.5,
     "audio": "tension_build", "curve": "ramp_up"},
    {"trigger": "merge", "offset": 0.0, "duration": 0.4,
     "audio": "swell_hit", "curve": "spike"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {"dot1": "", "dot2": "", "result": ""}
NEEDS_CONTENT = False
DEPRECATED = True


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    # Ported verbatim from biopunk._choreo_dot_merge.
    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    params = {}
    for cue in cue_words:
        params.update(cue.get("params", {}))
    d1 = params.get("dot1", "A")
    d2 = params.get("dot2", "B")
    pathways = params.get("pathways", [])
    if isinstance(pathways, str):
        pathways = [pathways]
    pw = " + ".join(pathways) if pathways else ""
    result = params.get("result", "")
    pw_code = ""
    if pw:
        pw_code = f'''
        pw = Text("{pw}", font="Courier", color=CYAN).scale(0.3)
        pw.move_to(UP * 2)
        self.play(FadeIn(pw), run_time=0.5)'''
    result_code = ""
    if result:
        result_code = f'''
        res = Text("{result}", font="Courier", color=GLOW, weight=BOLD).scale(0.8)
        res.move_to(UP * 0.5)
        self.play(FadeIn(res, scale=1.3), run_time=0.8)
        throb_title(self, res, cycles=2, scale_factor=1.05, cycle_time=0.8)'''
    return f'''        # Dot merge: {d1} + {d2}
        d1 = Dot(LEFT * 4, radius=0.15, color=PURPLE)
        d2 = Dot(RIGHT * 4, radius=0.15, color=GOLD)
        l1 = Text("{d1}", font="Courier", color=PURPLE, weight=BOLD).scale(0.3)
        l2 = Text("{d2}", font="Courier", color=GOLD, weight=BOLD).scale(0.3)
        l1.next_to(d1, DOWN, buff=0.2)
        l2.next_to(d2, DOWN, buff=0.2)
        self.play(FadeIn(d1), FadeIn(d2), FadeIn(l1), FadeIn(l2), run_time=1.0){pw_code}
        self.play(d1.animate.move_to(LEFT * 0.3), d2.animate.move_to(RIGHT * 0.3),
                  l1.animate.move_to(DOWN * 1.5 + LEFT * 2),
                  l2.animate.move_to(DOWN * 1.5 + RIGHT * 2), run_time=2.0)
        flash = Dot(ORIGIN, radius=0.3, color=GLOW).set_opacity(0.8)
        self.play(FadeIn(flash, scale=3.0), run_time=0.5){result_code}
        alive_wait(self, {max(duration - 7.0, 1.0):.1f}, particles=bg)'''
