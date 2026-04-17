"""tree — hierarchical layout (horizontal default, radial optional)."""

NAME = "tree"
DESCRIPTION = "Hierarchical tree with auto layout, depth-first reveal"
CUE_EVENTS = {"reveal_root", "reveal_level", "highlight_node"}
AUDIO_SPANS = [
    {"trigger": "reveal_root", "offset": 0.0, "duration": 0.5,
     "audio": "swoosh", "curve": "ease_in"},
    {"trigger": "reveal_level", "offset": 0.0, "duration": 0.4,
     "audio": "tick", "curve": "ease_in"},
    {"trigger": "highlight_node", "offset": 0.0, "duration": 0.3,
     "audio": "blip", "curve": "spike"},
]
DATA_SCHEMA = {
    "required": ["root"],
    "types": {"root": dict, "layout": str, "node_style": str},
    "enums": {"layout": {"horizontal", "vertical", "radial"},
              "node_style": {"dot", "box", "label"}},
}
PARAMS = {}
NEEDS_CONTENT = False
DEPRECATED = False


def _leaf_count(node: dict) -> int:
    children = node.get("children") or []
    if not children:
        return 1
    return sum(_leaf_count(c) for c in children)


def _depth(node: dict) -> int:
    children = node.get("children") or []
    if not children:
        return 0
    return 1 + max(_depth(c) for c in children)


def _layout(root: dict, layout: str = "horizontal") -> dict:
    """Return dict of id(node) -> (x, y) for every node.

    Horizontal: root on the left, children columns marching right, siblings
    stacked vertically proportional to their leaf count.
    Vertical: root on top, children rows going down.
    Radial: root at center, children spread in a full-circle arc weighted
    by leaf count.
    """
    import math
    positions: dict[int, tuple[float, float]] = {}
    max_d = max(_depth(root), 1)

    if layout == "radial":
        def place(node, a0, a1, depth):
            ang = (a0 + a1) / 2
            r = depth * (4.5 / max_d)
            positions[id(node)] = (r * math.cos(ang), r * math.sin(ang))
            kids = node.get("children") or []
            if not kids:
                return
            leaves = [_leaf_count(k) for k in kids]
            total = sum(leaves) or 1
            a = a0
            for kid, lc in zip(kids, leaves):
                span = (a1 - a0) * (lc / total)
                place(kid, a, a + span, depth + 1)
                a += span
        place(root, 0, 2 * math.pi, 0)
        return positions

    horizontal = (layout != "vertical")
    span = 4.5

    def place(node, d, lo, hi):
        mid = (lo + hi) / 2
        depth_pos = -span + (2 * span) * (d / max(max_d, 1))
        if horizontal:
            positions[id(node)] = (depth_pos, mid)
        else:
            positions[id(node)] = (mid, -depth_pos)
        kids = node.get("children") or []
        if not kids:
            return
        leaves = [_leaf_count(k) for k in kids]
        total = sum(leaves) or 1
        a = lo
        for kid, lc in zip(kids, leaves):
            width = (hi - lo) * (lc / total)
            place(kid, d + 1, a, a + width)
            a += width

    spread = 3.0
    place(root, 0, -spread, spread)
    return positions


def _walk(node, positions, parent_pos, lines, idx, node_style):
    label = str(node.get("label", "")).replace('"', '\\"')
    emph = bool(node.get("emphasized", False))
    x, y = positions[id(node)]
    col = "GOLD" if emph else "GLOW"
    lines.append(f'        n_{idx[0]} = Dot([{x:.3f}, {y:.3f}, 0], color={col}, radius=0.09)\n')
    lines.append(
        f'        lbl_{idx[0]} = Text("{label}", font="Courier", color={col}).scale(0.3)\n'
        f'        lbl_{idx[0]}.next_to(n_{idx[0]}, UP if {y} >= 0 else DOWN, buff=0.12)\n'
    )
    if parent_pos is not None:
        px, py = parent_pos
        lines.append(
            f'        edge_{idx[0]} = Line([{px:.3f}, {py:.3f}, 0], [{x:.3f}, {y:.3f}, 0],\n'
            f'                              color=TEXT_DIM, stroke_width=1.5)\n'
            f'        self.play(Create(edge_{idx[0]}), FadeIn(n_{idx[0]}), FadeIn(lbl_{idx[0]}),\n'
            f'                  run_time=0.3)\n'
        )
    else:
        lines.append(
            f'        self.play(FadeIn(n_{idx[0]}, scale=1.5), FadeIn(lbl_{idx[0]}), run_time=0.4)\n'
        )
    idx[0] += 1
    for kid in node.get("children") or []:
        _walk(kid, positions, (x, y), lines, idx, node_style)


def render(clip: dict, duration: float, images_dir: str, theme) -> str:
    visuals = clip.get("visuals", {})
    data = visuals.get("data") or {}
    root = data.get("root")
    if not root:
        return f"        alive_wait(self, {max(duration, 0.5):.2f}, particles=bg)\n"
    layout = data.get("layout", "horizontal")
    node_style = data.get("node_style", "dot")
    positions = _layout(root, layout=layout)

    lines: list[str] = []
    idx = [0]
    _walk(root, positions, None, lines, idx, node_style)
    node_count = idx[0]
    spent = 0.4 + node_count * 0.35
    hold = max(duration - spent - 1.0, 0.5)
    lines.append(f'        alive_wait(self, {hold:.2f}, particles=bg)\n')
    return "".join(lines)
