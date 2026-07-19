from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

"""
Vehicle ladder-frame FEM generator.

Builds a deterministic OptiStruct model of a truck-style ladder frame with
two longitudinal rails linked by several cross beams. Compared to the
first version this script:

* Uses a finer mesh (50 mm rail stations instead of 100 mm) and a finer
  cross-section z-discretisation (20 mm through the rail height).
* Adds a fourth cross beam, with non-uniform spacing along the frame
  (no two cross beams sit at equivalent stations).
* Lets each cross beam have different elevations (z_bot / z_top) and a
  twisted top wall, so several parts of the deck are no longer perfectly
  flat and the resulting stress field contains multiple hotspots per case.
* Splits the model into 24 components (one HMNAME COMP + PSHELL per physical
  wall), so the workbench "capture per component" feature has a meaningful
  target set: 8 rail walls (RAIL{L|R}_{TOP|BOT|OUTER|INNER}) and 16 cross
  beam walls (CB{n}_{TOP|BOT|WEB_LO|WEB_HI}).
* Combines multiple separated FORCE cards per SUBCASE so that, for every
  load case, the stress field simultaneously peaks at several distinct
  cross-beam / rail junctions along the frame. This is the key change
  that lets the workbench deduplicate_hotspots routine return multiple
  genuine top-N hotspots per subcase instead of one dominant peak.

Geometry summary
----------------
Frame length (X)             : 4000 mm, meshed every 50 mm  (81 stations)
Rail cross-section          : rectangular tube 130 mm wide x 120 mm tall
                              (y outer = +-680, y inner = +-550, z = 0..120)
Rail z subdivisions          : 0, 20, 40, 60, 80, 100, 120   (20 mm pitch)
Cross beams (4)             : width along X and elevation differ per beam
                              CB1 x=1000  width=100  z_bot=0   z_top=80  (plain)
                              CB2 x=1825  width=250  z_bot=40  z_top=120 (dropped top)
                              CB3 x=2725  width=250  z_bot=20  z_top 80->120 (twisted forward)
                              CB4 x=3575  width=150  z_bot=0   z_top 120->80 (twisted backward)
Cross beam Y span           : from y=-550 to y=+550 (rail inner-webs)
                              with shared-node welding to the inner webs.

Units: mm-N-MPa-tonne-s.
"""


def _text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:.12g}"
        if "." not in text and "e" not in text.lower():
            text += "."
        return text
    return str(value)


def free_card(name: str, *values: object | None) -> list[str]:
    """Format an OptiStruct free-field (comma-delimited) card."""
    fields = [_text(value) for value in values]
    while fields and fields[-1] == "":
        fields.pop()
    if not fields:
        return [name]
    lines = [",".join([name, *fields[:8]])]
    for index in range(8, len(fields), 8):
        lines.append(",".join(["+", *fields[index : index + 8]]))
    return lines


@dataclass(slots=True)
class FrameDeck:
    nodes: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    coord_to_id: dict[tuple[float, float, float], int] = field(default_factory=dict)
    elements: list[tuple[int, int, tuple[int, ...]]] = field(default_factory=list)
    next_node_id: int = 1
    next_element_id: int = 100001
    node_lines: list[str] = field(default_factory=list)
    element_lines: list[str] = field(default_factory=list)

    def get_or_add_node(self, xyz: tuple[float, float, float]) -> int:
        key = (round(xyz[0], 6), round(xyz[1], 6), round(xyz[2], 6))
        existing = self.coord_to_id.get(key)
        if existing is not None:
            return existing
        node_id = self.next_node_id
        self.next_node_id += 1
        self.nodes[node_id] = xyz
        self.coord_to_id[key] = node_id
        self.node_lines.extend(free_card("GRID", node_id, None, *xyz))
        return node_id

    def add_quad(self, pid: int, n1: int, n2: int, n3: int, n4: int) -> int:
        elem_id = self.next_element_id
        self.next_element_id += 1
        self.elements.append((elem_id, pid, (n1, n2, n3, n4)))
        self.element_lines.extend(free_card("CQUAD4", elem_id, pid, n1, n2, n3, n4))
        return elem_id


def add_shell_grid(
    deck: FrameDeck,
    pid: int,
    point: Callable[[int, int], tuple[float, float, float]],
    ni: int,
    nj: int,
) -> None:
    """Create a (ni+1) x (nj+1) grid of shared nodes in (i, j) parametric
    space and connect with CQUAD4 elements. Adjacent grids share nodes
    automatically through the coordinate cache inside ``FrameDeck``.
    """
    grid: list[list[int]] = []
    for i in range(ni + 1):
        row: list[int] = []
        for j in range(nj + 1):
            row.append(deck.get_or_add_node(point(i, j)))
        grid.append(row)
    for i in range(ni):
        for j in range(nj):
            n1 = grid[i][j]
            n2 = grid[i + 1][j]
            n3 = grid[i + 1][j + 1]
            n4 = grid[i][j + 1]
            deck.add_quad(pid, n1, n2, n3, n4)


# ---------------------------------------------------------------------------
# Geometry constants
# ---------------------------------------------------------------------------

FRAME_LENGTH = 4000.0
RAIL_X_STEP = 50.0
RAIL_NX = int(FRAME_LENGTH / RAIL_X_STEP)  # 80 segments -> 81 stations

RAIL_Y_OUTER = 680.0
RAIL_Y_INNER = 550.0
RAIL_Z_LIST = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0]
RAIL_NZ = len(RAIL_Z_LIST) - 1  # 6 segments through the height

CB_Y_LEFT = -550.0
CB_Y_RIGHT = 550.0
CB_Y_STEP = 50.0
CB_NY = int((CB_Y_RIGHT - CB_Y_LEFT) / CB_Y_STEP)  # 22 segments -> 23 nodes

MID_STEEL = 1
LOAD_SET_BASE = 200
LOAD_COMBINE_BASE = 300
SPC_ID = 100


# ---------------------------------------------------------------------------
# Component table
#
# Each physical wall of every part is its own PSHELL + HMNAME COMP, so the
# workbench can take per-component captures without any element-set editing.
#  - 8 rail walls   : RAIL{L|R}_{TOP|BOT|OUTER|INNER}
#  - 16 beam walls  : CB{n}_{TOP|BOT|WEB_LO|WEB_HI}
# total = 24 components.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Component:
    pid: int
    name: str
    thickness: float


PID_RAIL_L_TOP = 111
PID_RAIL_L_BOT = 112
PID_RAIL_L_OUT = 113
PID_RAIL_L_IN = 114
PID_RAIL_R_TOP = 121
PID_RAIL_R_BOT = 122
PID_RAIL_R_OUT = 123
PID_RAIL_R_IN = 124

COMPONENTS: dict[int, Component] = {
    PID_RAIL_L_TOP: Component(PID_RAIL_L_TOP, "RAIL_LEFT_TOP", 4.0),
    PID_RAIL_L_BOT: Component(PID_RAIL_L_BOT, "RAIL_LEFT_BOT", 4.0),
    PID_RAIL_L_OUT: Component(PID_RAIL_L_OUT, "RAIL_LEFT_OUTER", 3.5),
    PID_RAIL_L_IN: Component(PID_RAIL_L_IN, "RAIL_LEFT_INNER", 3.5),
    PID_RAIL_R_TOP: Component(PID_RAIL_R_TOP, "RAIL_RIGHT_TOP", 4.0),
    PID_RAIL_R_BOT: Component(PID_RAIL_R_BOT, "RAIL_RIGHT_BOT", 4.0),
    PID_RAIL_R_OUT: Component(PID_RAIL_R_OUT, "RAIL_RIGHT_OUTER", 3.5),
    PID_RAIL_R_IN: Component(PID_RAIL_R_IN, "RAIL_RIGHT_INNER", 3.5),
}


@dataclass(frozen=True, slots=True)
class CrossBeamSpec:
    """Geometry + 4 wall component ids for one cross beam."""
    name: str
    x_lo: float
    x_hi: float
    x_step: float
    z_bot: float
    z_top_lo: float  # z_top at x_lo
    z_top_hi: float  # z_top at x_hi  (different from z_top_lo => twisted top wall)
    z_step: float
    pid_top: int
    pid_bot: int
    pid_web_lo: int
    pid_web_hi: int


# Helper to allocate a CB's 4 wall components.
def _cb_components(idx: int, base: int) -> dict[str, int]:
    pids = {name: base + k for k, name in enumerate(("TOP", "BOT", "WEB_LO", "WEB_HI"))}
    for name, pid in pids.items():
        COMPONENTS[pid] = Component(
            pid,
            f"CB{idx}_{name}",
            # Top and bottom walls slightly thicker than the webs for hotspot diversity.
            3.0 if name in ("WEB_LO", "WEB_HI") else 3.5,
        )
    return pids


CB1_PIDS = _cb_components(1, 211)
CB2_PIDS = _cb_components(2, 221)
CB3_PIDS = _cb_components(3, 231)
CB4_PIDS = _cb_components(4, 241)

CB_SPECS: tuple[CrossBeamSpec, ...] = (
    CrossBeamSpec(
        name="CROSS_BEAM_1",
        x_lo=950.0, x_hi=1050.0, x_step=50.0,
        z_bot=0.0, z_top_lo=80.0, z_top_hi=80.0, z_step=20.0,
        pid_top=CB1_PIDS["TOP"], pid_bot=CB1_PIDS["BOT"],
        pid_web_lo=CB1_PIDS["WEB_LO"], pid_web_hi=CB1_PIDS["WEB_HI"],
    ),
    CrossBeamSpec(
        name="CROSS_BEAM_2",
        x_lo=1700.0, x_hi=1950.0, x_step=50.0,
        z_bot=40.0, z_top_lo=120.0, z_top_hi=120.0, z_step=20.0,
        pid_top=CB2_PIDS["TOP"], pid_bot=CB2_PIDS["BOT"],
        pid_web_lo=CB2_PIDS["WEB_LO"], pid_web_hi=CB2_PIDS["WEB_HI"],
    ),
    CrossBeamSpec(
        name="CROSS_BEAM_3",
        x_lo=2600.0, x_hi=2850.0, x_step=50.0,
        z_bot=20.0, z_top_lo=80.0, z_top_hi=120.0, z_step=20.0,
        pid_top=CB3_PIDS["TOP"], pid_bot=CB3_PIDS["BOT"],
        pid_web_lo=CB3_PIDS["WEB_LO"], pid_web_hi=CB3_PIDS["WEB_HI"],
    ),
    CrossBeamSpec(
        name="CROSS_BEAM_4",
        x_lo=3500.0, x_hi=3650.0, x_step=50.0,
        z_bot=0.0, z_top_lo=120.0, z_top_hi=80.0, z_step=20.0,
        pid_top=CB4_PIDS["TOP"], pid_bot=CB4_PIDS["BOT"],
        pid_web_lo=CB4_PIDS["WEB_LO"], pid_web_hi=CB4_PIDS["WEB_HI"],
    ),
)


# ---------------------------------------------------------------------------
# Geometry construction
# ---------------------------------------------------------------------------


def _add_rail(deck: FrameDeck, pids: dict[str, int], side: str) -> None:
    """Build one rail as four shell walls, each placed in a distinct component."""
    sign = -1.0 if side == "left" else 1.0
    y_outer = sign * RAIL_Y_OUTER
    y_inner = sign * RAIL_Y_INNER

    nx = RAIL_NX

    # Top plate
    add_shell_grid(
        deck,
        pids["TOP"],
        lambda i, j: (i * RAIL_X_STEP, y_outer + (y_inner - y_outer) * j, RAIL_Z_LIST[-1]),
        nx,
        1,
    )
    # Bottom plate
    add_shell_grid(
        deck,
        pids["BOT"],
        lambda i, j: (i * RAIL_X_STEP, y_outer + (y_inner - y_outer) * j, RAIL_Z_LIST[0]),
        nx,
        1,
    )
    # Outer web
    add_shell_grid(
        deck,
        pids["OUTER"],
        lambda i, j: (i * RAIL_X_STEP, y_outer, RAIL_Z_LIST[j]),
        nx,
        RAIL_NZ,
    )
    # Inner web
    add_shell_grid(
        deck,
        pids["INNER"],
        lambda i, j: (i * RAIL_X_STEP, y_inner, RAIL_Z_LIST[j]),
        nx,
        RAIL_NZ,
    )


def _z_top_at(spec: CrossBeamSpec, x: float) -> float:
    if spec.x_hi == spec.x_lo:
        return spec.z_top_lo
    t = (x - spec.x_lo) / (spec.x_hi - spec.x_lo)
    return spec.z_top_lo + t * (spec.z_top_hi - spec.z_top_lo)


def _add_cross_beam(deck: FrameDeck, spec: CrossBeamSpec) -> None:
    """Build one cross beam as a (possibly twisted) box section.

    Walls:
        - Top wall    : z varies linearly with x when z_top_lo != z_top_hi
        - Bottom wall : flat at z_bot
        - Front web   : at x_lo, planar, from z_bot up to z_top_lo
        - Back web    : at x_hi, planar, from z_bot up to z_top_hi
    """
    nx = int(round((spec.x_hi - spec.x_lo) / spec.x_step))
    ny = CB_NY
    nz_front = int(round((_z_top_at(spec, spec.x_lo) - spec.z_bot) / spec.z_step))
    nz_back = int(round((_z_top_at(spec, spec.x_hi) - spec.z_bot) / spec.z_step))

    def pt_top(i: int, j: int) -> tuple[float, float, float]:
        x = spec.x_lo + i * spec.x_step
        y = CB_Y_LEFT + j * CB_Y_STEP
        return (x, y, _z_top_at(spec, x))

    def pt_bot(i: int, j: int) -> tuple[float, float, float]:
        x = spec.x_lo + i * spec.x_step
        y = CB_Y_LEFT + j * CB_Y_STEP
        return (x, y, spec.z_bot)

    def pt_web_front(i: int, j: int) -> tuple[float, float, float]:
        # i indexes Y, j indexes Z from bot to z_top_lo
        y = CB_Y_LEFT + i * CB_Y_STEP
        z_top = _z_top_at(spec, spec.x_lo)
        z = spec.z_bot + (z_top - spec.z_bot) * j / nz_front
        return (spec.x_lo, y, z)

    def pt_web_back(i: int, j: int) -> tuple[float, float, float]:
        y = CB_Y_LEFT + i * CB_Y_STEP
        z_top = _z_top_at(spec, spec.x_hi)
        z = spec.z_bot + (z_top - spec.z_bot) * j / nz_back
        return (spec.x_hi, y, z)

    add_shell_grid(deck, spec.pid_top, pt_top, nx, ny)
    add_shell_grid(deck, spec.pid_bot, pt_bot, nx, ny)
    add_shell_grid(deck, spec.pid_web_lo, pt_web_front, ny, nz_front)
    add_shell_grid(deck, spec.pid_web_hi, pt_web_back, ny, nz_back)


@dataclass(slots=True)
class FramePayload:
    deck: FrameDeck
    lines: list[str]
    manifest: dict[str, object]


def build_frame() -> FramePayload:
    deck = FrameDeck()

    _add_rail(
        deck,
        {"TOP": PID_RAIL_L_TOP, "BOT": PID_RAIL_L_BOT,
         "OUTER": PID_RAIL_L_OUT, "INNER": PID_RAIL_L_IN},
        "left",
    )
    _add_rail(
        deck,
        {"TOP": PID_RAIL_R_TOP, "BOT": PID_RAIL_R_BOT,
         "OUTER": PID_RAIL_R_OUT, "INNER": PID_RAIL_R_IN},
        "right",
    )
    for spec in CB_SPECS:
        _add_cross_beam(deck, spec)

    # --- Pick load application nodes --------------------------------------
    def node_at(x: float, y: float, z: float) -> int:
        return deck.get_or_add_node((x, y, z))

    cb1_load = node_at(1000.0, 0.0, _z_top_at(CB_SPECS[0], 1000.0))  # (1000, 0, 80)
    cb2_load = node_at(1850.0, 0.0, _z_top_at(CB_SPECS[1], 1850.0))  # (1850, 0, 120)
    cb3_load = node_at(2750.0, 0.0, _z_top_at(CB_SPECS[2], 2750.0))  # (2750, 0, 104)
    cb4_load = node_at(3600.0, 0.0, _z_top_at(CB_SPECS[3], 3600.0))  # (3600, 0, 93.33...)

    mid_frame_left = node_at(2200.0, -RAIL_Y_INNER, RAIL_Z_LIST[-1])   # (2200, -550, 120)
    mid_frame_right = node_at(2200.0, RAIL_Y_INNER, RAIL_Z_LIST[-1])   # (2200, +550, 120)

    center_left_top = node_at(2000.0, -RAIL_Y_INNER, RAIL_Z_LIST[-1])  # (2000, -550, 120)
    center_right_top = node_at(2000.0, RAIL_Y_INNER, RAIL_Z_LIST[-1])  # (2000, +550, 120)
    front_left_top = node_at(200.0, -RAIL_Y_INNER, RAIL_Z_LIST[-1])    # (200, -550, 120)
    front_right_top = node_at(200.0, RAIL_Y_INNER, RAIL_Z_LIST[-1])    # (200, +550, 120)
    rear_left_top = node_at(3800.0, -RAIL_Y_INNER, RAIL_Z_LIST[-1])    # (3800, -550, 120)
    rear_right_top = node_at(3800.0, RAIL_Y_INNER, RAIL_Z_LIST[-1])    # (3800, +550, 120)

    # --- Constraints: 4 corner support nodes ------------------------------
    spc_nodes = [
        node_at(0.0, -RAIL_Y_INNER, 0.0),
        node_at(0.0, RAIL_Y_INNER, 0.0),
        node_at(FRAME_LENGTH, -RAIL_Y_INNER, 0.0),
        node_at(FRAME_LENGTH, RAIL_Y_INNER, 0.0),
    ]
    constraint_lines: list[str] = []
    constraint_lines.extend(free_card("SPC1", SPC_ID, 123456, *spc_nodes))
    constraint_lines.extend(free_card("SPCADD", SPC_ID + 1, SPC_ID))

    # --- Loads ------------------------------------------------------------
    load_lines: list[str] = []

    def add_force(sid: int, nid: int, mag: float, fx: float, fy: float, fz: float) -> None:
        load_lines.extend(free_card("FORCE", sid, nid, 0, mag, fx, fy, fz))

    bending_mag = 5000.0   # N, downward on each cross beam
    frame_bend_mag = 6000.0  # N, downward on each rail at mid-frame
    torsion_mag = 4000.0    # N, opposite signs on left/right rails
    bend_cb_shrink = 0.7    # scale cross-beam force in mixed bend/torsion cases

    # Each SUBCASE combines multiple FORCE cards applied at separated X
    # stations so the stress field peaks at several distinct
    # cross-beam / rail junctions simultaneously. Combined cases mix
    # bending and torsion so peaks appear on both rails near each loaded
    # station -- the worker's deduplicate_hotspots (which keeps the
    # highest value per component / minimum-distance neighborhood) then
    # returns multiple top-N hotspots rather than a single dominant one.

    # Subcase 1 : front pair cross-beam bending -> peaks near CB1 and CB2
    add_force(LOAD_SET_BASE + 1, cb1_load, bending_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 1, cb2_load, bending_mag, 0.0, 0.0, -1.0)

    # Subcase 2 : rear pair cross-beam bending -> peaks near CB3 and CB4
    add_force(LOAD_SET_BASE + 2, cb3_load, bending_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 2, cb4_load, bending_mag, 0.0, 0.0, -1.0)

    # Subcase 3 : every cross beam bent at once -> 4 separated peaks
    add_force(LOAD_SET_BASE + 3, cb1_load, bending_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 3, cb2_load, bending_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 3, cb3_load, bending_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 3, cb4_load, bending_mag, 0.0, 0.0, -1.0)

    # Subcase 4 : mid-frame rail bend + CB2 + CB3 -> peaks on rails and cross beams
    add_force(LOAD_SET_BASE + 4, mid_frame_left, frame_bend_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 4, mid_frame_right, frame_bend_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 4, cb2_load, bending_mag * bend_cb_shrink, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 4, cb3_load, bending_mag * bend_cb_shrink, 0.0, 0.0, -1.0)

    # Subcase 5 : centre torsion + mid-frame bend -> torsion peaks + mid bend peaks
    add_force(LOAD_SET_BASE + 5, center_left_top, torsion_mag, 0.0, 0.0, 1.0)
    add_force(LOAD_SET_BASE + 5, center_right_top, torsion_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 5, mid_frame_left, frame_bend_mag * 0.5, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 5, mid_frame_right, frame_bend_mag * 0.5, 0.0, 0.0, -1.0)

    # Subcase 6 : front torsion + CB1 bend -> twisted peaks at front + rail bend at CB1
    add_force(LOAD_SET_BASE + 6, front_left_top, torsion_mag, 0.0, 0.0, 1.0)
    add_force(LOAD_SET_BASE + 6, front_right_top, torsion_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 6, cb1_load, bending_mag * bend_cb_shrink, 0.0, 0.0, -1.0)

    # Subcase 7 : rear torsion + CB4 bend -> twisted peaks at rear + rail bend at CB4
    add_force(LOAD_SET_BASE + 7, rear_left_top, torsion_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 7, rear_right_top, torsion_mag, 0.0, 0.0, 1.0)
    add_force(LOAD_SET_BASE + 7, cb4_load, bending_mag * bend_cb_shrink, 0.0, 0.0, -1.0)

    # Subcase 8 : global twist -- front + rear opposite torsion -> 4 distinct peaks
    add_force(LOAD_SET_BASE + 8, front_left_top, torsion_mag, 0.0, 0.0, 1.0)
    add_force(LOAD_SET_BASE + 8, front_right_top, torsion_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 8, rear_left_top, torsion_mag, 0.0, 0.0, -1.0)
    add_force(LOAD_SET_BASE + 8, rear_right_top, torsion_mag, 0.0, 0.0, 1.0)

    # LOAD combine cards: SID, overall_scale, (per_set_scale, set_id) pairs
    for i in range(1, 9):
        load_lines.extend(
            free_card("LOAD", LOAD_COMBINE_BASE + i, 1.0, 1.0, LOAD_SET_BASE + i)
        )

    # --- Case control ----------------------------------------------------
    subcase_defs: list[tuple[int, str, str]] = [
        (1, "FRONT_CB_PAIR_BEND",   f"  LOAD = {LOAD_COMBINE_BASE + 1}"),
        (2, "REAR_CB_PAIR_BEND",    f"  LOAD = {LOAD_COMBINE_BASE + 2}"),
        (3, "ALL_CB_BEND",          f"  LOAD = {LOAD_COMBINE_BASE + 3}"),
        (4, "MID_FRAME_COMB_BEND",  f"  LOAD = {LOAD_COMBINE_BASE + 4}"),
        (5, "CENTER_TORSION_BEND",  f"  LOAD = {LOAD_COMBINE_BASE + 5}"),
        (6, "FRONT_TORSION_BEND",   f"  LOAD = {LOAD_COMBINE_BASE + 6}"),
        (7, "REAR_TORSION_BEND",    f"  LOAD = {LOAD_COMBINE_BASE + 7}"),
        (8, "GLOBAL_TORSION",       f"  LOAD = {LOAD_COMBINE_BASE + 8}"),
    ]

    case_control: list[str] = [
        "$ Generated by tools/generate_vehicle_frame.py",
        "$ Vehicle ladder frame (2 rails + 4 cross beams) for HMReport testing.",
        "$ Units: mm, N, MPa, tonne, second",
        "TITLE = VEHICLE LADDER FRAME DEMO MODEL",
        "ECHO = NONE",
        "FORMAT,H3D",
        "DISPLACEMENT(H3D) = ALL",
        "STRESS(H3D,CORNER) = ALL",
        "STRAIN(H3D) = ALL",
        "ELFORCE(H3D) = ALL",
    ]
    for sid, label, load_line in subcase_defs:
        case_control.extend(
            [
                f"SUBCASE {sid}",
                f"  LABEL = {label}",
                "  ANALYSIS = STATICS",
                f"  SPC = {SPC_ID}",
                load_line,
            ]
        )
    case_control.append("BEGIN BULK")

    # Components live in the global COMPONENTS table: one PSHELL + one
    # HMNAME COMP per wall, named "<part>_<wall>" so workbench captures
    # can pick e.g. just RAIL_LEFT_INNER or just CB3_WEB_HI.
    component_comments = [
        f'{"$HMNAME":<8}{"COMP":<16}{comp.pid:>8}"{comp.name}"'
        for comp in sorted(COMPONENTS.values(), key=lambda c: c.pid)
    ]

    material_lines: list[str] = []
    material_lines.extend(free_card("MAT1", MID_STEEL, 210000.0, 80769.2308, 0.3, 7.85e-9, 350.0, 260.0))

    property_lines: list[str] = []
    for comp in sorted(COMPONENTS.values(), key=lambda c: c.pid):
        property_lines.extend(free_card("PSHELL", comp.pid, MID_STEEL, comp.thickness, MID_STEEL))

    bulk_lines: list[str] = []
    bulk_lines.extend(component_comments)
    bulk_lines.append("$ --- MATERIALS ---")
    bulk_lines.extend(material_lines)
    bulk_lines.append("$ --- PROPERTIES ---")
    bulk_lines.extend(property_lines)
    bulk_lines.append("$ --- NODES ---")
    bulk_lines.extend(deck.node_lines)
    bulk_lines.append("$ --- ELEMENTS ---")
    bulk_lines.extend(deck.element_lines)
    bulk_lines.append("$ --- CONSTRAINTS ---")
    bulk_lines.extend(constraint_lines)
    bulk_lines.append("$ --- LOADS ---")
    bulk_lines.extend(load_lines)

    full_lines = [*case_control, *bulk_lines, "ENDDATA"]

    quads = sum(1 for _, _, nids in deck.elements if len(nids) == 4)

    cb_summaries = []
    for spec in CB_SPECS:
        cb_summaries.append(
            {
                "name": spec.name,
                "pids": {
                    "top": spec.pid_top,
                    "bot": spec.pid_bot,
                    "web_lo": spec.pid_web_lo,
                    "web_hi": spec.pid_web_hi,
                },
                "x_lo": spec.x_lo,
                "x_hi": spec.x_hi,
                "x_center": (spec.x_lo + spec.x_hi) / 2.0,
                "width_along_x": spec.x_hi - spec.x_lo,
                "z_bot": spec.z_bot,
                "z_top_lo": spec.z_top_lo,
                "z_top_hi": spec.z_top_hi,
                "twisted": spec.z_top_lo != spec.z_top_hi,
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/generate_vehicle_frame.py",
        "solver": {
            "name": "OptiStruct",
            "compatibility_target": "2019+",
            "unit_system": "mm-N-MPa-tonne-s",
        },
        "geometry": {
            "frame_length_mm": FRAME_LENGTH,
            "rail_x_station_mm": RAIL_X_STEP,
            "rail_width_mm": RAIL_Y_OUTER - RAIL_Y_INNER,
            "rail_height_mm": RAIL_Z_LIST[-1] - RAIL_Z_LIST[0],
            "rail_pitch_mm": 2 * RAIL_Y_INNER,
            "rail_z_subdivisions": RAIL_Z_LIST,
            "cross_beam_y_span_mm": [CB_Y_LEFT, CB_Y_RIGHT],
        },
        "cross_beams": cb_summaries,
        "subcases": [
            {"id": 1, "label": "FRONT_CB_PAIR_BEND", "analysis": "STATICS",
             "description": "5 kN downward on top centres of CB1 (x=1000) and CB2 (x=1850) simultaneously; stress peaks form near both front cross-beam / rail junctions."},
            {"id": 2, "label": "REAR_CB_PAIR_BEND", "analysis": "STATICS",
             "description": "5 kN downward on top centres of CB3 (x=2750) and CB4 (x=3600) simultaneously; stress peaks form near both rear cross-beam / rail junctions."},
            {"id": 3, "label": "ALL_CB_BEND", "analysis": "STATICS",
             "description": "5 kN downward on top centres of all four cross beams at once; produces four separated stress peaks along the frame length."},
            {"id": 4, "label": "MID_FRAME_COMB_BEND", "analysis": "STATICS",
             "description": "6 kN downward on both rail tops at x=2200 plus 3.5 kN on CB2 and CB3; peaks at mid-frame plus on the two middle cross beams."},
            {"id": 5, "label": "CENTER_TORSION_BEND", "analysis": "STATICS",
             "description": "Opposite +/-4 kN vertical loads on left/right rails at x=2000 combined with 3 kN downward on each rail at x=2200; produces torsion peaks plus a mid-frame bending peak."},
            {"id": 6, "label": "FRONT_TORSION_BEND", "analysis": "STATICS",
             "description": "Opposite +/-4 kN vertical loads on left/right rails at x=200 combined with 3.5 kN downward on CB1 (x=1000); peaks at front-end torsion station and at the CB1 / rail junctions."},
            {"id": 7, "label": "REAR_TORSION_BEND", "analysis": "STATICS",
             "description": "Opposite +/-4 kN vertical loads on left/right rails at x=3800 combined with 3.5 kN downward on CB4 (x=3600); peaks at rear-end torsion station and at the CB4 / rail junctions."},
            {"id": 8, "label": "GLOBAL_TORSION", "analysis": "STATICS",
             "description": "Opposite vertical +/-4 kN at the front (x=200) and opposite signs at the rear (x=3800); four separated torsion peaks form at both ends of the frame."},
        ],
        "loads": {
            "bending_force_n": bending_mag,
            "frame_bending_force_n": frame_bend_mag,
            "torsion_force_n": torsion_mag,
            "load_set_ids": [LOAD_SET_BASE + i for i in range(1, 9)],
        },
        "constraints": {
            "spc_id": SPC_ID,
            "fixed_dofs": "123456",
            "support_nodes": [
                {"node_id": nid, "x": deck.nodes[nid][0], "y": deck.nodes[nid][1], "z": deck.nodes[nid][2]}
                for nid in spc_nodes
            ],
        },
        "expected_counts": {
            "nodes": len(deck.nodes),
            "elements": len(deck.elements),
            "quads": quads,
            "components": len(COMPONENTS),
            "subcases": 8,
        },
        "components": [
            {"id": comp.pid, "name": comp.name, "property_type": "PSHELL",
             "material": MID_STEEL, "thickness": comp.thickness}
            for comp in sorted(COMPONENTS.values(), key=lambda c: c.pid)
        ],
        "hotspot_design_notes": (
            "Per-subcase multi-hotspot behaviour is achieved by (1) leaving most of "
            "the frame free between four corner supports so loads excite global bending "
            "and torsion; (2) giving each cross beam a different elevation, twist and "
            "shell thickness, so stress peaks do not coincide; (3) mesh refinement at "
            "50 mm rail pitch + 20 mm rail z-pitch so stress gradients are resolved "
            "across many elements; (4) welded shared-node connections between cross "
            "beams and inner webs, which produce junction stress concentrations at "
            "every rail/cross-beam intersection along the load path; and (5) combining "
            "multiple FORCE cards within each SUBCASE so that separated load "
            "stations simultaneously generate stress peaks at distinct cross-beam / "
            "rail junctions. Because the worker's deduplicate_hotspots keeps only the "
            "highest value per component / minimum-distance neighborhood, applying "
            "loads at several separated X stations (rather than one) is what makes "
            "top_n reliably yield multiple distinct hotspots for every subcase."
        ),
    }
    return FramePayload(deck=deck, lines=full_lines, manifest=manifest)


def generate_model(output: Path) -> dict[str, object]:
    payload = build_frame()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(payload.lines) + "\n", encoding="utf-8", newline="\n")
    manifest = {**payload.manifest, "artifacts": {
        "fem": output.name,
        "manifest": f"{output.stem}.manifest.json",
    }}
    manifest_path = output.with_name(f"{output.stem}.manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a vehicle ladder-frame OptiStruct model with multiple "
                    "bending and torsion subcases for HMReport testing."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/vehicle_frame/vehicle_frame.fem"),
        help="Output FEM path (default: examples/vehicle_frame/vehicle_frame.fem)",
    )
    args = parser.parse_args()
    manifest = generate_model(args.output)
    expected_obj = manifest["expected_counts"]
    assert isinstance(expected_obj, dict)
    expected: dict[str, object] = expected_obj
    print(f"Generated {args.output.resolve()}")
    print(
        f"  nodes={expected['nodes']} elements={expected['elements']} "
        f"quads={expected['quads']} subcases={expected['subcases']}"
    )
    print(f"  manifest {args.output.resolve().with_name(str(manifest['artifacts']['manifest']))}")  # type: ignore[index]


if __name__ == "__main__":
    main()