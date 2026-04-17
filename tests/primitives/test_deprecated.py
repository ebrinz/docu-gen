import ast
from docugen.themes.primitives import dot_merge, remove_reveal


def test_dot_merge_deprecated_flagged():
    assert dot_merge.DEPRECATED is True


def test_remove_reveal_deprecated_flagged():
    assert remove_reveal.DEPRECATED is True


def test_dot_merge_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "dot_merge",
                        "cue_words": [{"event": "show_dot1", "at_index": 0,
                                       "params": {"dot1": "A", "dot2": "B",
                                                  "result": "C"}}]}}
    body = dot_merge.render(clip, duration=10.0, images_dir="/tmp", theme=None)
    assert isinstance(body, str) and body.strip()
    ast.parse("def construct(self):\n" + body)


def test_remove_reveal_render_compiles():
    clip = {"clip_id": "x", "text": "",
            "word_times": [{"word": "x", "start": 0, "end": 0.3}],
            "visuals": {"slide_type": "remove_reveal",
                        "cue_words": [{"event": "remove", "at_index": 0,
                                       "params": {"removed": "A", "emerged": "B",
                                                  "via": "C"}}]}}
    body = remove_reveal.render(clip, duration=10.0, images_dir="/tmp", theme=None)
    assert isinstance(body, str) and body.strip()
    ast.parse("def construct(self):\n" + body)
