"""chapter_card — animated chapter marker. Migrated from biopunk._choreo_chapter_card
with no behavior change."""

NAME = "chapter_card"
DESCRIPTION = "Chapter number + title, imperial border draws in"
CUE_EVENTS = {"reveal_number", "reveal_title"}
AUDIO_SPANS = [
    {"trigger": "reveal_title", "offset": -0.5, "duration": 0.8,
     "audio": "swoosh", "curve": "ease_in"},
]
DATA_SCHEMA = {"required": [], "types": {}}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    cue_words = visuals.get("cue_words", [])
    params = {}
    for cue in cue_words:
        params.update(cue.get("params", {}))
    num = params.get("num", "00")
    title = params.get("title", "UNTITLED")
    return f'''        # Chapter card
        ch_num = Text("{num}", font="Courier", color=SITH_RED, weight=BOLD).scale(1.5)
        ch_title = Text("{title}", font="Courier", color=GLOW, weight=BOLD).scale(0.9)
        ch_title.next_to(ch_num, RIGHT, buff=0.4)
        card = VGroup(ch_num, ch_title).move_to(ORIGIN)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=1.0)
        throb_title(self, ch_title, cycles=2, scale_factor=1.03, cycle_time=1.0)
        alive_wait(self, {max(duration - 4.0, 0.5):.1f}, particles=bg)'''
