#!/usr/bin/env python3
"""
IRON SEPULCHRE WALKER — RESONANCE VISUALIZER v2.2
Gothic industrial audio oscilloscope with live JACK input.
Battle-scarred steel aesthetic.  By iron and will.
"""

import argparse
import math
import sys
import os
import time
from collections import deque, OrderedDict
import threading

# ── Platform (must run before pygame/GL import) ──────────────────────────────
def _configure_platform() -> None:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
        os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
        print("ℹ  Wayland session detected.")
_configure_platform()

import pygame
from pygame.locals import (
    DOUBLEBUF, OPENGL, QUIT, KEYDOWN, RESIZABLE,
    K_ESCAPE, K_t, K_g, K_s, K_b, K_h, K_f, K_p,
    K_PLUS, K_EQUALS, K_MINUS, K_KP_PLUS, K_KP_MINUS,
)
from OpenGL.GL import *
import jack
import numpy as np


# ═══════════════════════════════════════════════════════════════
# ARGUMENT PARSING
# ═══════════════════════════════════════════════════════════════
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Iron Sepulchre Walker — Resonance Visualizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Runtime hotkeys:
  T          Cycle colour theme
  B          Cycle waveform mode (oscilloscope / spectrum / both)
  G          Toggle grid overlay
  S          Toggle CRT scanlines
  F          Toggle fullscreen
  + / -      Increase / decrease input gain
  H          Show / hide help overlay
  Escape     Quit
""")
    p.add_argument("--theme",        default="iron",
                   choices=list(THEMES.keys()),
                   help="Colour theme (default: iron)")
    p.add_argument("--gain",         type=float, default=1.0, metavar="X",
                   help="Input gain multiplier (default: 1.0)")
    p.add_argument("--unit-name",    default="IRON SEPULCHRE Mk.IV", metavar="NAME",
                   help="Unit designation shown in title banner")
    p.add_argument("--fps",          type=int, default=75,
                   help="Target frame rate cap (default: 75)")
    p.add_argument("--vsync",        action="store_true",
                   help="Enable VSync (SDL swap control). Overrides --fps cap when active.")
    p.add_argument("--busy-wait",    action="store_true",
                   help="Use busy-loop for tighter FPS timing (higher CPU, lower latency)")
    p.add_argument("--borderless",   action="store_true",
                   help="Borderless/windowless mode — no title bar or window chrome")
    p.add_argument("--no-scanlines", action="store_true",
                   help="Disable CRT scanlines")
    p.add_argument("--no-grid",      action="store_true",
                   help="Disable oscilloscope grid")
    p.add_argument("--waveform",     default="oscilloscope",
                   choices=["oscilloscope", "spectrum", "both"],
                   help="Waveform display mode (default: oscilloscope)")
    p.add_argument("--persistence", type=int, default=0, metavar="N",
                   help="Phosphor trail frames 0–32 (default: 0 = off)")
    p.add_argument("--width",        type=int, default=1280,
                   help="Window width in pixels (default: 1280)")
    p.add_argument("--height",       type=int, default=720,
                   help="Window height in pixels (default: 720)")
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════
# COLOUR THEMES
# ═══════════════════════════════════════════════════════════════
THEMES = {
    # ── Originals ──────────────────────────────────────────────────────────
    "iron": {           # scorched forge-amber — battle-worn default
        "screen_bg":  (0.000, 0.028, 0.005),
        "wave_outer": (1.000, 0.350, 0.000),
        "wave_mid":   (1.000, 0.620, 0.040),
        "wave_inner": (1.000, 0.800, 0.200),
        "wave_core":  (1.000, 0.940, 0.680),
        "eye_iris":   (0.900, 0.030, 0.030),
        "eye_hot":    (1.000, 0.450, 0.150),
        "gauge_lo":   (0.480, 0.300, 0.015),
        "gauge_mid":  (1.000, 0.350, 0.000),
        "gauge_hi":   (0.900, 0.030, 0.030),
        "grid":       (0.060, 0.200, 0.080),
        "beat_flash": (1.000, 0.600, 0.100),
    },
    "void": {           # deep-space sensor cyan
        "screen_bg":  (0.000, 0.000, 0.055),
        "wave_outer": (0.000, 0.280, 0.700),
        "wave_mid":   (0.050, 0.620, 0.950),
        "wave_inner": (0.300, 0.820, 1.000),
        "wave_core":  (0.750, 0.970, 1.000),
        "eye_iris":   (0.000, 0.650, 1.000),
        "eye_hot":    (0.500, 0.900, 1.000),
        "gauge_lo":   (0.000, 0.200, 0.500),
        "gauge_mid":  (0.000, 0.500, 0.900),
        "gauge_hi":   (0.000, 0.800, 1.000),
        "grid":       (0.030, 0.080, 0.200),
        "beat_flash": (0.200, 0.800, 1.000),
    },
    "plague": {         # corrupted virescent toxin
        "screen_bg":  (0.000, 0.040, 0.000),
        "wave_outer": (0.080, 0.380, 0.000),
        "wave_mid":   (0.250, 0.700, 0.050),
        "wave_inner": (0.500, 0.920, 0.150),
        "wave_core":  (0.820, 1.000, 0.550),
        "eye_iris":   (0.200, 0.820, 0.100),
        "eye_hot":    (0.700, 1.000, 0.300),
        "gauge_lo":   (0.050, 0.280, 0.020),
        "gauge_mid":  (0.200, 0.600, 0.050),
        "gauge_hi":   (0.500, 0.950, 0.100),
        "grid":       (0.040, 0.120, 0.020),
        "beat_flash": (0.600, 1.000, 0.200),
    },
    "gold": {           # consecrated white-hot divine
        "screen_bg":  (0.040, 0.020, 0.000),
        "wave_outer": (0.850, 0.480, 0.000),
        "wave_mid":   (1.000, 0.760, 0.100),
        "wave_inner": (1.000, 0.920, 0.500),
        "wave_core":  (1.000, 1.000, 0.900),
        "eye_iris":   (1.000, 0.750, 0.000),
        "eye_hot":    (1.000, 1.000, 0.600),
        "gauge_lo":   (0.500, 0.280, 0.000),
        "gauge_mid":  (1.000, 0.650, 0.050),
        "gauge_hi":   (1.000, 0.950, 0.400),
        "grid":       (0.120, 0.080, 0.020),
        "beat_flash": (1.000, 1.000, 0.500),
    },
    # ── New palettes ────────────────────────────────────────────────────────
    "chaos": {          # warp-corrupted magenta/violet — reality unravelling
        "screen_bg":  (0.025, 0.000, 0.045),
        "wave_outer": (0.500, 0.000, 0.800),
        "wave_mid":   (0.750, 0.050, 0.900),
        "wave_inner": (0.950, 0.250, 1.000),
        "wave_core":  (1.000, 0.700, 1.000),
        "eye_iris":   (0.700, 0.000, 1.000),
        "eye_hot":    (1.000, 0.400, 1.000),
        "gauge_lo":   (0.250, 0.000, 0.400),
        "gauge_mid":  (0.600, 0.020, 0.700),
        "gauge_hi":   (0.950, 0.100, 1.000),
        "grid":       (0.100, 0.020, 0.150),
        "beat_flash": (1.000, 0.300, 1.000),
    },
    "frost": {          # glacial cryo-field — permafrost blue-white
        "screen_bg":  (0.000, 0.008, 0.035),
        "wave_outer": (0.050, 0.350, 0.700),
        "wave_mid":   (0.200, 0.600, 0.900),
        "wave_inner": (0.600, 0.860, 1.000),
        "wave_core":  (0.920, 0.980, 1.000),
        "eye_iris":   (0.400, 0.780, 1.000),
        "eye_hot":    (0.850, 0.970, 1.000),
        "gauge_lo":   (0.040, 0.200, 0.480),
        "gauge_mid":  (0.200, 0.560, 0.820),
        "gauge_hi":   (0.700, 0.920, 1.000),
        "grid":       (0.040, 0.120, 0.250),
        "beat_flash": (0.800, 0.960, 1.000),
    },
    "lava": {           # volcanic magma flows — superheated basalt
        "screen_bg":  (0.040, 0.000, 0.000),
        "wave_outer": (0.600, 0.020, 0.000),
        "wave_mid":   (0.900, 0.180, 0.000),
        "wave_inner": (1.000, 0.500, 0.050),
        "wave_core":  (1.000, 0.900, 0.400),
        "eye_iris":   (0.950, 0.100, 0.000),
        "eye_hot":    (1.000, 0.600, 0.050),
        "gauge_lo":   (0.380, 0.010, 0.000),
        "gauge_mid":  (0.800, 0.150, 0.000),
        "gauge_hi":   (1.000, 0.480, 0.020),
        "grid":       (0.150, 0.030, 0.000),
        "beat_flash": (1.000, 0.700, 0.100),
    },
    "bone": {           # reliquary ivory — ancient dust and dried parchment
        "screen_bg":  (0.028, 0.020, 0.008),
        "wave_outer": (0.380, 0.300, 0.160),
        "wave_mid":   (0.620, 0.520, 0.300),
        "wave_inner": (0.850, 0.760, 0.520),
        "wave_core":  (1.000, 0.960, 0.800),
        "eye_iris":   (0.720, 0.580, 0.300),
        "eye_hot":    (1.000, 0.920, 0.680),
        "gauge_lo":   (0.250, 0.180, 0.080),
        "gauge_mid":  (0.580, 0.460, 0.240),
        "gauge_hi":   (0.900, 0.800, 0.580),
        "grid":       (0.100, 0.080, 0.040),
        "beat_flash": (1.000, 0.950, 0.750),
    },
    "nuclear": {        # reactor-core radiation — fissile yellow-green
        "screen_bg":  (0.000, 0.030, 0.000),
        "wave_outer": (0.200, 0.500, 0.000),
        "wave_mid":   (0.500, 0.820, 0.020),
        "wave_inner": (0.780, 1.000, 0.100),
        "wave_core":  (0.960, 1.000, 0.600),
        "eye_iris":   (0.500, 0.950, 0.050),
        "eye_hot":    (0.900, 1.000, 0.500),
        "gauge_lo":   (0.150, 0.380, 0.000),
        "gauge_mid":  (0.450, 0.780, 0.020),
        "gauge_hi":   (0.800, 1.000, 0.100),
        "grid":       (0.080, 0.180, 0.010),
        "beat_flash": (0.900, 1.000, 0.400),
    },
    "midnight": {       # deep indigo astropathic signal — starless purple-blue
        "screen_bg":  (0.000, 0.000, 0.030),
        "wave_outer": (0.080, 0.050, 0.400),
        "wave_mid":   (0.220, 0.150, 0.700),
        "wave_inner": (0.500, 0.380, 0.950),
        "wave_core":  (0.820, 0.760, 1.000),
        "eye_iris":   (0.350, 0.200, 0.900),
        "eye_hot":    (0.700, 0.600, 1.000),
        "gauge_lo":   (0.060, 0.040, 0.280),
        "gauge_mid":  (0.180, 0.120, 0.580),
        "gauge_hi":   (0.480, 0.360, 0.920),
        "grid":       (0.060, 0.040, 0.160),
        "beat_flash": (0.700, 0.600, 1.000),
    },
    # ── Extended palettes ───────────────────────────────────────────────────
    "phosphor": {       # classic P31 green phosphor CRT — terminal warmth
        "screen_bg":  (0.000, 0.018, 0.004),
        "wave_outer": (0.000, 0.220, 0.040),
        "wave_mid":   (0.020, 0.540, 0.080),
        "wave_inner": (0.150, 0.850, 0.200),
        "wave_core":  (0.700, 1.000, 0.750),
        "eye_iris":   (0.050, 0.700, 0.120),
        "eye_hot":    (0.450, 1.000, 0.550),
        "gauge_lo":   (0.010, 0.180, 0.030),
        "gauge_mid":  (0.040, 0.480, 0.070),
        "gauge_hi":   (0.150, 0.850, 0.200),
        "grid":       (0.020, 0.100, 0.025),
        "beat_flash": (0.600, 1.000, 0.700),
    },
    "ember": {          # dying forge-coal — deep smouldering amber-red
        "screen_bg":  (0.030, 0.008, 0.000),
        "wave_outer": (0.300, 0.040, 0.000),
        "wave_mid":   (0.600, 0.120, 0.000),
        "wave_inner": (0.900, 0.300, 0.020),
        "wave_core":  (1.000, 0.700, 0.200),
        "eye_iris":   (0.750, 0.080, 0.000),
        "eye_hot":    (1.000, 0.450, 0.050),
        "gauge_lo":   (0.220, 0.030, 0.000),
        "gauge_mid":  (0.550, 0.100, 0.000),
        "gauge_hi":   (0.900, 0.280, 0.010),
        "grid":       (0.090, 0.020, 0.000),
        "beat_flash": (1.000, 0.500, 0.050),
    },
    "mercury": {        # liquid-metal monochrome — cold precision silver
        "screen_bg":  (0.005, 0.008, 0.012),
        "wave_outer": (0.200, 0.230, 0.260),
        "wave_mid":   (0.420, 0.460, 0.500),
        "wave_inner": (0.700, 0.740, 0.780),
        "wave_core":  (0.950, 0.970, 1.000),
        "eye_iris":   (0.500, 0.540, 0.600),
        "eye_hot":    (0.880, 0.920, 1.000),
        "gauge_lo":   (0.150, 0.170, 0.200),
        "gauge_mid":  (0.380, 0.420, 0.460),
        "gauge_hi":   (0.750, 0.800, 0.860),
        "grid":       (0.080, 0.090, 0.110),
        "beat_flash": (1.000, 1.000, 1.000),
    },
    "plasma": {         # hot-pink discharge arc — superheated ionised gas
        "screen_bg":  (0.030, 0.000, 0.020),
        "wave_outer": (0.600, 0.000, 0.350),
        "wave_mid":   (0.880, 0.050, 0.500),
        "wave_inner": (1.000, 0.300, 0.700),
        "wave_core":  (1.000, 0.750, 0.920),
        "eye_iris":   (0.900, 0.020, 0.500),
        "eye_hot":    (1.000, 0.500, 0.800),
        "gauge_lo":   (0.350, 0.000, 0.200),
        "gauge_mid":  (0.700, 0.030, 0.380),
        "gauge_hi":   (1.000, 0.200, 0.600),
        "grid":       (0.120, 0.010, 0.080),
        "beat_flash": (1.000, 0.400, 0.800),
    },
    "abyss": {          # deep-ocean bioluminescence — pressurised teal darkness
        "screen_bg":  (0.000, 0.010, 0.020),
        "wave_outer": (0.000, 0.180, 0.260),
        "wave_mid":   (0.000, 0.380, 0.460),
        "wave_inner": (0.050, 0.680, 0.700),
        "wave_core":  (0.400, 0.950, 0.920),
        "eye_iris":   (0.000, 0.500, 0.560),
        "eye_hot":    (0.300, 0.900, 0.880),
        "gauge_lo":   (0.000, 0.120, 0.180),
        "gauge_mid":  (0.000, 0.320, 0.400),
        "gauge_hi":   (0.050, 0.650, 0.680),
        "grid":       (0.010, 0.080, 0.100),
        "beat_flash": (0.300, 1.000, 0.950),
    },
    "rust": {           # oxidised iron hull — pitted ferrous decay
        "screen_bg":  (0.022, 0.010, 0.005),
        "wave_outer": (0.340, 0.080, 0.010),
        "wave_mid":   (0.580, 0.180, 0.030),
        "wave_inner": (0.820, 0.340, 0.080),
        "wave_core":  (1.000, 0.620, 0.250),
        "eye_iris":   (0.650, 0.150, 0.020),
        "eye_hot":    (1.000, 0.500, 0.150),
        "gauge_lo":   (0.220, 0.055, 0.008),
        "gauge_mid":  (0.480, 0.140, 0.025),
        "gauge_hi":   (0.780, 0.300, 0.060),
        "grid":       (0.090, 0.030, 0.005),
        "beat_flash": (1.000, 0.550, 0.100),
    },
}
THEME_ORDER = list(THEMES.keys())

C_STEEL_BG   = (0.068, 0.062, 0.055)
C_STEEL_DARK = (0.100, 0.090, 0.080)
C_STEEL_MID  = (0.195, 0.178, 0.158)
C_STEEL_LITE = (0.375, 0.345, 0.298)
C_STEEL_HI   = (0.540, 0.495, 0.418)
C_GOLD       = (0.775, 0.615, 0.075)
C_GOLD_DARK  = (0.390, 0.295, 0.028)
C_BONE       = (0.748, 0.698, 0.578)


# ═══════════════════════════════════════════════════════════════
# LAYOUT  (ortho space 130 × 70)
# ═══════════════════════════════════════════════════════════════
W, H       = 130.0, 70.0
BAN_B      = 62.0
STAT_T     = 8.0
GAU_L,  GAU_R   = 2.0,  28.0
GAU2_L, GAU2_R  = 102.0, 128.0
SCR_L,  SCR_R   = 30.0,  100.0
SCR_B  = STAT_T + 1.0
SCR_T  = BAN_B  - 1.0
BOX_L  = SCR_L + 2.0;  BOX_R  = SCR_R - 2.0
BOX_B  = SCR_B + 14.0; BOX_T  = SCR_T - 2.0
CENTER_Y = (BOX_B + BOX_T) / 2.0

WAVE_AMP   = (BOX_T - BOX_B) * 0.22
BASE_FREQ  = 3.5
AUDIO_GAIN = (BOX_T - BOX_B) * 0.38
SINE_SPEED = 4.0
EYE_SPEED  = 8.0
NUM_POINTS = 512


# ═══════════════════════════════════════════════════════════════
# PRE-BAKED GEOMETRY  (computed once at import, zero trig per frame)
# ═══════════════════════════════════════════════════════════════
_N_CIRC = 32   # circle segment count
_CIRC_A = np.linspace(0.0, 2.0 * math.pi, _N_CIRC, endpoint=False, dtype=np.float32)
_CIRC_COS = np.cos(_CIRC_A)   # shape (32,)
_CIRC_SIN = np.sin(_CIRC_A)   # shape (32,)

# Waveform X coordinates — fixed, computed once
_WAVE_XS = (BOX_L + np.arange(NUM_POINTS, dtype=np.float32)
            * ((BOX_R - BOX_L) / (NUM_POINTS - 1)))
# Base sine argument per sample — the phase offset is added per frame
_WAVE_SINE_ARG = (2.0 * math.pi * BASE_FREQ
                  * np.arange(NUM_POINTS, dtype=np.float32) / NUM_POINTS)

# Pre-allocated waveform vertex buffer [x0,y0, x1,y1, ...]  shape (NUM_POINTS*2,)
_WAVE_VERTS = np.empty(NUM_POINTS * 2, dtype=np.float32)
_WAVE_VERTS[0::2] = _WAVE_XS   # X never changes; set once here

# Spectrum bin edges (computed once)
_N_BARS = 48
_SPEC_EDGES = np.round(np.linspace(0, NUM_POINTS // 2 + 1,
                                    _N_BARS + 1)).astype(np.int32)
_SPEC_COUNTS = np.diff(_SPEC_EDGES).clip(1).astype(np.float32)

# Scanline geometry — static QUADS vertex array
def _build_scanline_verts() -> np.ndarray:
    step = 0.88
    stripe = step * 0.42
    ys = np.arange(BOX_B, BOX_T, step, dtype=np.float32)
    n  = len(ys)
    v  = np.empty(n * 8, dtype=np.float32)
    # Each quad: BL, BR, TR, TL
    v[0::8] = BOX_L;        v[1::8] = ys
    v[2::8] = BOX_R;        v[3::8] = ys
    v[4::8] = BOX_R;        v[5::8] = ys + stripe
    v[6::8] = BOX_L;        v[7::8] = ys + stripe
    return v

_SCANLINE_VERTS = _build_scanline_verts()
_SCANLINE_N     = len(_SCANLINE_VERTS) // 2   # vertex count

# Grid geometry — static LINES vertex array
def _build_grid_verts() -> np.ndarray:
    verts = []
    gx = (BOX_R - BOX_L) / 7.0
    x = BOX_L + gx
    while x < BOX_R:
        verts += [x, BOX_B, x, BOX_T];  x += gx
    gy = (BOX_T - BOX_B) / 4.0
    y = BOX_B + gy
    while y < BOX_T:
        verts += [BOX_L, y, BOX_R, y];  y += gy
    # Centre crosshair
    cx2 = (BOX_L + BOX_R) / 2.0
    verts += [cx2, BOX_B, cx2, BOX_T, BOX_L, CENTER_Y, BOX_R, CENTER_Y]
    return np.array(verts, dtype=np.float32)

_GRID_VERTS = _build_grid_verts()
_GRID_N     = len(_GRID_VERTS) // 2


# ═══════════════════════════════════════════════════════════════
# RUNTIME STATE
# ═══════════════════════════════════════════════════════════════
class AppState:
    _PERSIST_STEPS = (0, 4, 8, 16)   # frames cycled by P hotkey

    def __init__(self, args: argparse.Namespace) -> None:
        self.theme_idx  = THEME_ORDER.index(args.theme)
        self.gain       = args.gain
        self.scanlines  = not args.no_scanlines
        self.grid       = not args.no_grid
        self.waveform   = args.waveform
        self.unit_name  = args.unit_name
        self.show_help  = False
        self.fullscreen = False
        self.vsync      = args.vsync
        self.borderless = args.borderless
        self.busy_wait  = args.busy_wait
        self.fps_target = args.fps
        self.fps_actual = 0.0
        self.beat_flash = 0.0
        # Persistence trail
        _p = max(0, min(args.persistence, 32))
        self.persistence: int = _p
        self._persist_idx: int = 0   # index into _PERSIST_STEPS for hotkey cycling
        # Pre-search for matching step
        for i, v in enumerate(self._PERSIST_STEPS):
            if v >= _p:
                self._persist_idx = i; break
        self.wave_trail: deque = deque(maxlen=max(1, self.persistence))
        # Smooth theme transitions — lerp from → to over _LERP_DUR seconds
        _base = THEMES[THEME_ORDER[self.theme_idx]]
        self._theme_from: dict = dict(_base)
        self._theme_to:   dict = dict(_base)
        self._lerp_t: float    = 1.0   # 1.0 = complete, no interpolation needed

    @property
    def theme(self) -> dict:
        """Returns current effective theme, interpolated during transition."""
        if self._lerp_t >= 1.0:
            return self._theme_to
        t = self._lerp_t
        return {k: tuple(a + (b - a) * t
                         for a, b in zip(self._theme_from[k], self._theme_to[k]))
                for k in self._theme_to}

    def advance_lerp(self, dt: float) -> None:
        if self._lerp_t < 1.0:
            self._lerp_t = min(1.0, self._lerp_t + dt * 5.0)   # ~0.20 s

    def cycle_theme(self) -> None:
        self._theme_from = self.theme          # freeze mid-lerp values
        self.theme_idx   = (self.theme_idx + 1) % len(THEME_ORDER)
        self._theme_to   = dict(THEMES[THEME_ORDER[self.theme_idx]])
        self._lerp_t     = 0.0

    def cycle_waveform(self) -> None:
        modes = ["oscilloscope", "spectrum", "both", "lissajous"]
        self.waveform = modes[(modes.index(self.waveform) + 1) % len(modes)]

    def cycle_persistence(self) -> None:
        self._persist_idx = (self._persist_idx + 1) % len(self._PERSIST_STEPS)
        self.persistence  = self._PERSIST_STEPS[self._persist_idx]
        self.wave_trail   = deque(maxlen=max(1, self.persistence))

    def nudge_gain(self, delta: float) -> None:
        self.gain = max(0.1, min(10.0, round(self.gain + delta, 2)))


# ═══════════════════════════════════════════════════════════════
# AUDIO STATE
# ═══════════════════════════════════════════════════════════════
class AudioState:
    _BEAT_WINDOW    = 40
    _BEAT_THRESH    = 1.55
    _BEAT_COOLDOWN  = 15          # frames to suppress re-trigger after a beat
    _BEAT_COOLDOWN = 8

    def __init__(self) -> None:
        self._lock        = threading.Lock()
        self._buffer_l    = deque(maxlen=NUM_POINTS * 4)   # left / mono
        self._buffer_r    = deque(maxlen=NUM_POINTS * 4)   # right channel
        self._rms         = 0.0
        self._peak        = 0.0
        self._rms_smooth  = 0.0
        self._energy_hist = deque([0.0] * self._BEAT_WINDOW,
                                  maxlen=self._BEAT_WINDOW)
        self._beat_cooldown_rem = 0
        self.beat_detected = False

    def push(self, data_l: np.ndarray,
             data_r: np.ndarray | None = None) -> None:
        if data_l.size == 0:
            return
        rms  = float(np.sqrt(np.mean(data_l ** 2)))
        peak = float(np.max(np.abs(data_l)))
        step = max(1, len(data_l) // NUM_POINTS)
        with self._lock:
            self._rms  = rms
            self._peak = peak
            self._buffer_l.extend(data_l[::step].tolist())
            if data_r is not None and data_r.size > 0:
                self._buffer_r.extend(data_r[::step].tolist())
            else:
                # Mirror L into R when only mono available
                self._buffer_r.extend(data_l[::step].tolist())

    def _get_arr(self, buf: deque) -> np.ndarray:
        with self._lock:
            raw = np.array(buf, dtype=np.float32)
        n = len(raw)
        if n >= NUM_POINTS:
            return raw[-NUM_POINTS:]
        out = np.zeros(NUM_POINTS, dtype=np.float32)
        out[-n:] = raw
        return out

    def snapshot(self) -> tuple[np.ndarray, float, float]:
        """Mono snapshot — left/primary channel."""
        with self._lock:
            buf  = np.array(self._buffer_l, dtype=np.float32)
            rms  = self._rms
            peak = self._peak
        n = len(buf)
        if n >= NUM_POINTS:
            samples = buf[-NUM_POINTS:]
        else:
            samples = np.zeros(NUM_POINTS, dtype=np.float32)
            samples[-n:] = buf

        self._rms_smooth += 0.18 * (rms - self._rms_smooth)

        self._energy_hist.append(rms)
        mean_e = sum(self._energy_hist) / len(self._energy_hist)
        if self._beat_cooldown_rem > 0:
            self._beat_cooldown_rem -= 1
        if (rms > mean_e * self._BEAT_THRESH
                and rms > 0.004
                and self._beat_cooldown_rem == 0):
            self.beat_detected = True
            self._beat_cooldown_rem = self._BEAT_COOLDOWN
        else:
            self.beat_detected = False

        return samples, self._rms_smooth, peak

    def snapshot_stereo(self) -> tuple[np.ndarray, np.ndarray, float, float]:
        """Return (left, right, rms_smooth, peak) — for Lissajous mode."""
        with self._lock:
            buf_l = np.array(self._buffer_l, dtype=np.float32)
            buf_r = np.array(self._buffer_r, dtype=np.float32)
            rms, peak = self._rms, self._peak

        def _pad(arr):
            n = len(arr)
            if n >= NUM_POINTS: return arr[-NUM_POINTS:]
            out = np.zeros(NUM_POINTS, dtype=np.float32)
            out[-n:] = arr; return out

        return _pad(buf_l), _pad(buf_r), self._rms_smooth, peak


# ═══════════════════════════════════════════════════════════════
# JACK CLIENT
# ═══════════════════════════════════════════════════════════════
def create_jack_client(state: AudioState) -> jack.Client:
    try:
        client  = jack.Client("iron-sepulchre-viz")
        inport_l = client.inports.register("audio_in_L")
        inport_r = client.inports.register("audio_in_R")
    except jack.JackError as exc:
        raise RuntimeError(
            "Failed to connect to audio server.\n"
            "  Ensure PipeWire-JACK is running: qjackctl   or   pw-jack …"
        ) from exc

    @client.set_process_callback
    def _process(_frames: int) -> None:
        l = client.inports[0].get_array()
        r = client.inports[1].get_array()
        state.push(l, r)

    client.activate()
    phys = client.get_ports(is_physical=True, is_output=True, is_audio=True)
    for i, port in enumerate(phys[:2]):
        try:
            dest = inport_l if i == 0 else inport_r
            client.connect(port, dest)
            print(f"✓  Connected {port.name} → {dest.name}")
        except jack.JackError:
            pass
    if not phys:
        print("⚠  No physical audio ports found — connect manually in qjackctl.")
    return client


# ═══════════════════════════════════════════════════════════════
# GL VERTEX ARRAY HELPERS
# All geometry goes through glVertexPointer + glDrawArrays.
# Eliminates Python glVertex2f loops entirely.
# ═══════════════════════════════════════════════════════════════
def _va_draw(verts: np.ndarray, mode: int, n: int = -1) -> None:
    """Submit a float32 flat vertex array (x,y pairs) and draw it."""
    count = n if n >= 0 else len(verts) // 2
    glEnableClientState(GL_VERTEX_ARRAY)
    glVertexPointer(2, GL_FLOAT, 0, verts)
    glDrawArrays(mode, 0, count)
    glDisableClientState(GL_VERTEX_ARRAY)


def _circle_verts_fan(cx: float, cy: float, r: float) -> np.ndarray:
    """
    Build a TRIANGLE_FAN vertex array for a filled circle.
    Layout: [cx,cy,  x0,y0,  x1,y1, ..., x31,y31,  x0,y0]  (N+2 vertices)
    Uses pre-baked trig — zero cos/sin calls per invocation.
    """
    xs = cx + r * _CIRC_COS   # numpy broadcast: 32 muls instead of 32 cos()
    ys = cy + r * _CIRC_SIN
    v  = np.empty((_N_CIRC + 2) * 2, dtype=np.float32)
    v[0], v[1] = cx, cy
    v[2::2][: _N_CIRC] = xs
    v[3::2][: _N_CIRC] = ys
    v[-2], v[-1] = xs[0], ys[0]   # close fan
    return v


def _circle_verts_loop(cx: float, cy: float, r: float) -> np.ndarray:
    """Build a LINE_LOOP vertex array for a circle outline."""
    xs = cx + r * _CIRC_COS
    ys = cy + r * _CIRC_SIN
    v  = np.empty(_N_CIRC * 2, dtype=np.float32)
    v[0::2] = xs
    v[1::2] = ys
    return v


def filled_circle(cx: float, cy: float, r: float, _n: int = 32) -> None:
    _va_draw(_circle_verts_fan(cx, cy, r), GL_TRIANGLE_FAN, _N_CIRC + 2)

def outline_circle(cx: float, cy: float, r: float, _n: int = 32) -> None:
    _va_draw(_circle_verts_loop(cx, cy, r), GL_LINE_LOOP, _N_CIRC)


# ═══════════════════════════════════════════════════════════════
# BASIC PRIMITIVES  (immediate-mode for simple quads/lines)
# ═══════════════════════════════════════════════════════════════
def filled_rect(x1: float, y1: float, x2: float, y2: float) -> None:
    glBegin(GL_QUADS)
    glVertex2f(x1, y1); glVertex2f(x2, y1)
    glVertex2f(x2, y2); glVertex2f(x1, y2)
    glEnd()

def line_rect(x1: float, y1: float, x2: float, y2: float) -> None:
    glBegin(GL_LINE_LOOP)
    glVertex2f(x1, y1); glVertex2f(x2, y1)
    glVertex2f(x2, y2); glVertex2f(x1, y2)
    glEnd()

def grad_rect(x1, y1, x2, y2, c_bl, c_br, c_tr, c_tl) -> None:
    glBegin(GL_QUADS)
    glColor3f(*c_bl); glVertex2f(x1, y1)
    glColor3f(*c_br); glVertex2f(x2, y1)
    glColor3f(*c_tr); glVertex2f(x2, y2)
    glColor3f(*c_tl); glVertex2f(x1, y2)
    glEnd()


# ═══════════════════════════════════════════════════════════════
# TEXT — BOUNDED LRU TEXTURE CACHE
# Replaces per-frame glGenTextures/glTexImage2D/glDeleteTextures with
# a 64-slot LRU.  Old entries are evicted and their textures freed.
# Dynamic strings that change frequently stay hot in the cache.
# ═══════════════════════════════════════════════════════════════
_TEX_LRU_MAX = 64
_tex_lru: OrderedDict = OrderedDict()   # key → (tid, pixel_w, pixel_h)
_fonts:   dict        = {}

_current_width  = 1280
_current_height = 720


def _get_font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        for name in ("DejaVuSansMono", "FreeMono", "LiberationMono", None):
            try:
                f = (pygame.font.SysFont(name, size)
                     if name else pygame.font.Font(None, size))
                _fonts[size] = f
                break
            except Exception:
                continue
    return _fonts[size]


def _upload_texture(text: str, size: int, color: tuple) -> tuple[int, int, int]:
    font = _get_font(size)
    surf = font.render(text, True, color)
    data = pygame.image.tostring(surf, "RGBA", True)
    tw, th = surf.get_size()
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, data)
    return tid, tw, th


def draw_text(text: str, cx: float, cy: float, size: int = 12,
              color: tuple = (200, 170, 80), anchor: str = "center") -> None:
    key = (text, size, color)
    if key in _tex_lru:
        _tex_lru.move_to_end(key)
        tid, tw, th = _tex_lru[key]
    else:
        if len(_tex_lru) >= _TEX_LRU_MAX:
            _, evicted = _tex_lru.popitem(last=False)
            glDeleteTextures([evicted[0]])
        tid, tw, th = _upload_texture(text, size, color)
        _tex_lru[key] = (tid, tw, th)

    uw = tw * (W / _current_width)
    uh = th * (H / _current_height)
    if   anchor == "center": x1, y1 = cx - uw/2, cy - uh/2
    elif anchor == "left":   x1, y1 = cx,         cy - uh/2
    else:                    x1, y1 = cx - uw,     cy - uh/2

    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tid)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x1,    y1)
    glTexCoord2f(1, 0); glVertex2f(x1+uw, y1)
    glTexCoord2f(1, 1); glVertex2f(x1+uw, y1+uh)
    glTexCoord2f(0, 1); glVertex2f(x1,    y1+uh)
    glEnd()
    glDisable(GL_TEXTURE_2D)


# ═══════════════════════════════════════════════════════════════
# DECORATIVE COMPONENTS
# ═══════════════════════════════════════════════════════════════

def draw_steel_panel(x1, y1, x2, y2, raised: bool = True) -> None:
    grad_rect(x1, y1, x2, y2, C_STEEL_DARK, C_STEEL_DARK,
              C_STEEL_MID, C_STEEL_MID)
    bv = 0.75
    hi, sh = (C_STEEL_HI, C_STEEL_BG) if raised else (C_STEEL_BG, C_STEEL_HI)
    glColor3f(*hi)
    filled_rect(x1,    y2-bv, x2, y2)
    filled_rect(x1,    y1,    x1+bv, y2)
    glColor3f(*sh)
    filled_rect(x1,    y1,    x2, y1+bv)
    filled_rect(x2-bv, y1,    x2, y2)


def draw_rivet(cx: float, cy: float, r: float = 0.9) -> None:
    glColor3f(*C_STEEL_MID);  filled_circle(cx, cy, r)
    glColor3f(*C_STEEL_DARK); outline_circle(cx, cy, r)
    glColor4f(0.65, 0.60, 0.50, 0.90)
    # Highlight: small offset circle — use same vertex-array path, no extra trig
    filled_circle(cx - r * 0.28, cy + r * 0.32, r * 0.38)


def draw_rivet_row(x1, x2, y, step: float = 3.0) -> None:
    x = x1
    while x <= x2:
        draw_rivet(x, y);  x += step

def draw_rivet_col(x, y1, y2, step: float = 3.0) -> None:
    y = y1
    while y <= y2:
        draw_rivet(x, y);  y += step


def draw_gothic_arch(cx, y_base, y_apex, half_w) -> None:
    r   = half_w * 1.08
    lx  = cx + half_w * 0.50
    rx  = cx - half_w * 0.50
    steps = 28

    # Pre-compute both arcs as numpy arrays — no per-step math.cos in Python
    t_left  = np.linspace(math.pi,        math.pi * 0.52, steps + 1, dtype=np.float32)
    t_right = np.linspace(0.0,            math.pi * 0.48, steps + 1, dtype=np.float32)

    def _arc_verts(acx, acy, ts):
        v = np.empty((steps + 1) * 2, dtype=np.float32)
        v[0::2] = acx + r * np.cos(ts)
        v[1::2] = acy + r * np.sin(ts)
        return v

    glColor3f(*C_GOLD); glLineWidth(2.0)
    _va_draw(_arc_verts(lx, y_base, t_left),  GL_LINE_STRIP, steps + 1)
    _va_draw(_arc_verts(rx, y_base, t_right), GL_LINE_STRIP, steps + 1)

    ty = y_base + (y_apex - y_base) * 0.42
    tw = half_w * 0.52
    glBegin(GL_LINES)
    glVertex2f(cx - tw, ty); glVertex2f(cx + tw, ty)
    glEnd()

    oy  = y_base + (y_apex - y_base) * 0.72
    or_ = 1.15
    # Quatrefoil petals: 4 circles, angles precomputed
    for i in range(4):
        a  = math.pi / 2 + i * math.pi / 2
        px = cx + or_ * 0.85 * math.cos(a)
        py = oy + or_ * 0.85 * math.sin(a)
        glColor3f(*C_GOLD_DARK); filled_circle(px, py, or_ * 0.45)
        glColor3f(*C_GOLD);      outline_circle(px, py, or_ * 0.45)

    glColor3f(*C_GOLD_DARK); filled_circle(cx, oy, or_ * 0.55)
    glColor3f(*C_GOLD);      outline_circle(cx, oy, or_ * 0.55)
    glColor4f(1.0, 0.90, 0.50, 0.85)
    filled_circle(cx, oy, or_ * 0.28)
    glLineWidth(1.0)


def draw_skull(cx: float, cy: float, sz: float) -> None:
    glColor3f(*C_BONE)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx, cy + sz * 0.15)
    for i in range(13):
        a = math.pi + math.pi * i / 12
        glVertex2f(cx + sz*0.60*math.cos(a),
                   cy + sz*0.55*math.sin(a) + sz*0.15)
    glEnd()
    grad_rect(cx-sz*0.55, cy-sz*0.35, cx+sz*0.55, cy+sz*0.18,
              C_STEEL_MID, C_STEEL_MID, C_BONE, C_BONE)
    glColor3f(*C_STEEL_BG)
    filled_circle(cx-sz*0.22, cy+sz*0.05, sz*0.16)
    filled_circle(cx+sz*0.22, cy+sz*0.05, sz*0.16)
    filled_circle(cx-sz*0.06, cy-sz*0.10, sz*0.08)
    filled_circle(cx+sz*0.06, cy-sz*0.10, sz*0.08)
    glBegin(GL_TRIANGLES)
    glVertex2f(cx-sz*0.11, cy-sz*0.12)
    glVertex2f(cx+sz*0.11, cy-sz*0.12)
    glVertex2f(cx,          cy-sz*0.26)
    glEnd()
    tw = sz * 0.13
    for i in range(-2, 3):
        tx = cx + i * tw * 1.05
        glColor3f(*C_BONE)
        filled_rect(tx-tw*0.40, cy-sz*0.38, tx+tw*0.40, cy-sz*0.22)
        glColor3f(*C_STEEL_BG)
        glBegin(GL_LINES)
        glVertex2f(tx+tw*0.40, cy-sz*0.38)
        glVertex2f(tx+tw*0.40, cy-sz*0.22)
        glEnd()
    glColor3f(*C_STEEL_DARK); glLineWidth(1.2)
    outline_circle(cx, cy+sz*0.15, sz*0.60)
    glLineWidth(1.0)


def draw_iron_vow_seal(cx: float, cy: float,
                       w: float = 2.5, h: float = 5.0) -> None:
    glColor3f(0.65, 0.04, 0.04); filled_circle(cx, cy + h*0.25, w*0.55)
    glColor3f(0.35, 0.01, 0.01); glLineWidth(1.5)
    s = w * 0.28
    for dx, dy in [(s, s), (-s, s)]:
        glBegin(GL_LINES)
        glVertex2f(cx-dx, cy+h*0.25-dy)
        glVertex2f(cx+dx, cy+h*0.25+dy)
        glEnd()
    glColor3f(0.68, 0.63, 0.50)
    filled_rect(cx-w*0.22, cy-h*0.50, cx+w*0.22, cy+h*0.25)
    glColor3f(0.52, 0.48, 0.36)
    for i in range(3):
        ry = cy - h*0.50 + i * h*0.25
        glBegin(GL_LINES)
        glVertex2f(cx-w*0.22, ry); glVertex2f(cx+w*0.22, ry)
        glEnd()
    glLineWidth(1.0)


def draw_warning_lamp(cx: float, cy: float, lit: bool,
                      rms: float, t: float, phase: float = 0.0,
                      color_on:  tuple = (1.0, 0.12, 0.04),
                      color_off: tuple = (0.25, 0.02, 0.01)) -> None:
    pulse  = (math.sin(t * 5.8 + phase) + 1) * 0.5
    bright = min(pulse + rms * 2.5, 1.0) if lit else 0.0

    glColor3f(*C_STEEL_DARK); filled_circle(cx, cy, 1.75)
    glColor3f(*C_STEEL_MID);  outline_circle(cx, cy, 1.75)

    if lit:
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glColor4f(*color_on, bright * 0.88)
        filled_circle(cx, cy, 1.35)
        glColor4f(1.0, 0.9*bright, 0.4*bright, bright * 0.45)
        filled_circle(cx, cy, 0.65)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    else:
        glColor3f(*color_off)
        filled_circle(cx, cy, 1.0)

    glColor4f(1.0, 1.0, 1.0, 0.28)
    filled_circle(cx - 0.45, cy + 0.48, 0.38)


def draw_vertical_gauge(x1, y1, x2, y2,
                        level: float, peak_hold: float,
                        theme: dict) -> None:
    """
    24-segment VU column.
    Batches all dim segments, then all lit segments grouped by colour tier —
    3 glDrawArrays calls instead of 48 individual filled_rect calls.
    """
    n, gap, mg = 24, 0.45, 1.1
    seg_h = (y2 - y1 - mg*2 - gap*(n-1)) / n

    # Pre-compute all segment y1/y2
    seg_y1 = y1 + mg + np.arange(n, dtype=np.float32) * (seg_h + gap)
    seg_y2 = seg_y1 + seg_h
    fracs  = np.arange(n, dtype=np.float32) / n
    ix = x1 + mg;  ax = x2 - mg

    def _rects_verts(mask: np.ndarray) -> np.ndarray:
        """Build a GL_QUADS vertex array for selected segments."""
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            return None
        v = np.empty(len(idxs) * 8, dtype=np.float32)
        v[0::8] = ix;        v[1::8] = seg_y1[idxs]
        v[2::8] = ax;        v[3::8] = seg_y1[idxs]
        v[4::8] = ax;        v[5::8] = seg_y2[idxs]
        v[6::8] = ix;        v[7::8] = seg_y2[idxs]
        return v

    lit = fracs < level

    # Dim segments (one batch)
    dim_v = _rects_verts(~lit)
    if dim_v is not None:
        glColor3f(*C_STEEL_DARK); _va_draw(dim_v, GL_QUADS)
        glColor4f(0, 0, 0, 0.55);  _va_draw(dim_v, GL_QUADS)

    # Lit segments — three colour tiers (lo/mid/hi), each one batch
    for mask, c in [
        (lit & (fracs <= 0.55), theme["gauge_lo"]),
        (lit & (fracs >  0.55) & (fracs <= 0.80), theme["gauge_mid"]),
        (lit & (fracs >  0.80), theme["gauge_hi"]),
    ]:
        v = _rects_verts(mask)
        if v is not None:
            glColor3f(*c); _va_draw(v, GL_QUADS)

    # Highlights on lit segments (single batch)
    if np.any(lit):
        idxs = np.where(lit)[0]
        hv   = np.empty(len(idxs) * 8, dtype=np.float32)
        hv[0::8] = ix;  hv[1::8] = seg_y2[idxs] - 0.25
        hv[2::8] = ax;  hv[3::8] = seg_y2[idxs] - 0.25
        hv[4::8] = ax;  hv[5::8] = seg_y2[idxs]
        hv[6::8] = ix;  hv[7::8] = seg_y2[idxs]
        glColor4f(1, 1, 1, 0.10); _va_draw(hv, GL_QUADS)

    # Tick marks — one GL_LINES call
    tick_verts = []
    for i in range(0, n+1, 6):
        ty = y1 + mg + i * (seg_h + gap)
        tick_verts += [x1, ty, ix, ty, ax, ty, x2, ty]
    glColor3f(*C_STEEL_HI); glLineWidth(1.0)
    _va_draw(np.array(tick_verts, dtype=np.float32), GL_LINES)

    # Peak-hold tick
    if peak_hold > 0.01:
        py = y1 + mg + peak_hold * n * (seg_h + gap)
        glColor3f(*theme["gauge_hi"]); glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex2f(x1+mg*0.5, py); glVertex2f(x2-mg*0.5, py)
        glEnd()
        glLineWidth(1.0)


# ═══════════════════════════════════════════════════════════════
# SCREEN CONTENT
# ═══════════════════════════════════════════════════════════════

def draw_screen_bg(appst: AppState) -> None:
    theme = appst.theme
    glColor3f(*theme["screen_bg"]); filled_rect(BOX_L, BOX_B, BOX_R, BOX_T)

    if appst.grid:
        glColor4f(*theme["grid"], 0.40); glLineWidth(0.5)
        _va_draw(_GRID_VERTS, GL_LINES, _GRID_N)

    if appst.scanlines:
        glColor4f(0, 0, 0, 0.20)
        _va_draw(_SCANLINE_VERTS, GL_QUADS, _SCANLINE_N)

    # Corner vignettes — 4 triangles
    for (vx, vy), (dx, dy) in [
        ((BOX_L, BOX_B), (1, 1)),  ((BOX_R, BOX_B), (-1, 1)),
        ((BOX_R, BOX_T), (-1,-1)), ((BOX_L, BOX_T), (1, -1))
    ]:
        vw = (BOX_R - BOX_L) * 0.22;  vh = (BOX_T - BOX_B) * 0.22
        glColor4f(0, 0, 0, 0.52)
        glBegin(GL_TRIANGLES)
        glVertex2f(vx, vy)
        glVertex2f(vx + dx*vw, vy)
        glVertex2f(vx, vy + dy*vh)
        glEnd()

    # Beat flash — additive inner border glow
    if appst.beat_flash > 0.001:
        bf = appst.beat_flash
        fc = theme["beat_flash"]
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        # Outer halo ring
        glColor4f(*fc, bf * 0.35)
        filled_rect(BOX_L, BOX_B, BOX_R, BOX_B + 2.5)
        filled_rect(BOX_L, BOX_T - 2.5, BOX_R, BOX_T)
        filled_rect(BOX_L, BOX_B, BOX_L + 2.5, BOX_T)
        filled_rect(BOX_R - 2.5, BOX_B, BOX_R, BOX_T)
        # Screen-wide flash at peak intensity
        glColor4f(*fc, bf * 0.07)
        filled_rect(BOX_L, BOX_B, BOX_R, BOX_T)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glLineWidth(1.0)


def draw_waveform_oscilloscope(samples: np.ndarray, rms: float,
                                sine_phase: float, appst: AppState) -> None:
    """
    4-pass additive bloom waveform with optional phosphor persistence trail.
    """
    gain = AUDIO_GAIN * appst.gain * (1.0 + rms * 3.2)
    th   = appst.theme

    sine_y = WAVE_AMP * np.sin(_WAVE_SINE_ARG + sine_phase)
    ys = np.clip(CENTER_Y + sine_y + samples * gain,
                 BOX_B + 1.0, BOX_T - 1.0).astype(np.float32)

    # ── Phosphor persistence trail ────────────────────────────────────────
    if appst.persistence > 0:
        trail = list(appst.wave_trail)   # oldest first
        n_trail = len(trail)
        if n_trail > 0:
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
            for i, old_ys in enumerate(trail):
                age   = (i + 1) / (n_trail + 1)   # 0→1 oldest→newest
                alpha = age * 0.28                 # max 0.28, falls off at tail
                _WAVE_VERTS[1::2] = old_ys
                glLineWidth(1.2)
                glColor4f(*th["wave_inner"], alpha)
                _va_draw(_WAVE_VERTS, GL_LINE_STRIP, NUM_POINTS)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        appst.wave_trail.append(ys.copy())

    # ── Current frame (4-pass bloom) ─────────────────────────────────────
    _WAVE_VERTS[1::2] = ys

    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    for width, color, alpha in (
        (7.0, th["wave_outer"], 0.055),
        (4.5, th["wave_mid"],   0.140),
        (2.5, th["wave_inner"], 0.420),
        (1.2, th["wave_core"],  0.920),
    ):
        glLineWidth(width)
        glColor4f(*color, alpha)
        _va_draw(_WAVE_VERTS, GL_LINE_STRIP, NUM_POINTS)

    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLineWidth(1.0)


def draw_waveform_spectrum(samples: np.ndarray, rms: float,
                            appst: AppState) -> None:
    """
    FFT spectrum as 48 vertical bars.
    Fully vectorised: numpy handles windowing, FFT, and bin averaging.
    Bar vertex arrays submitted in 3 batches (glow, core, cap) instead of
    per-bar immediate-mode calls.
    """
    if len(samples) < 16:
        return

    window = np.hanning(NUM_POINTS).astype(np.float32)
    fft    = np.abs(np.fft.rfft(samples * window))
    fft    = np.log1p(fft * appst.gain * 0.15)
    mx     = fft.max()
    if mx > 1e-6:
        fft /= mx

    # Vectorised bin averaging via reduceat (single numpy call, no Python loop)
    bin_sums = np.add.reduceat(fft, _SPEC_EDGES[:-1])
    mags     = np.minimum(bin_sums / _SPEC_COUNTS, 1.0)

    bar_gap = 0.4
    bar_w   = (BOX_R - BOX_L) / _N_BARS - bar_gap
    bxs     = BOX_L + np.arange(_N_BARS, dtype=np.float32) * (bar_w + bar_gap)
    by1_all = np.full(_N_BARS, BOX_B + 1.0, dtype=np.float32)
    by2_all = (BOX_B + 1.0 + mags * (BOX_T - BOX_B - 2.0)).astype(np.float32)

    th = appst.theme
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)

    # Glow rects — all bars in one QUADS call
    gv = np.empty(_N_BARS * 8, dtype=np.float32)
    gv[0::8] = bxs - 0.3;           gv[1::8] = by1_all
    gv[2::8] = bxs + bar_w + 0.3;   gv[3::8] = by1_all
    gv[4::8] = bxs + bar_w + 0.3;   gv[5::8] = by2_all
    gv[6::8] = bxs - 0.3;           gv[7::8] = by2_all
    glColor4f(*th["wave_outer"], 0.12); _va_draw(gv, GL_QUADS)

    # Core bars — all in one QUADS call
    cv = np.empty(_N_BARS * 8, dtype=np.float32)
    cv[0::8] = bxs;          cv[1::8] = by1_all
    cv[2::8] = bxs + bar_w;  cv[3::8] = by1_all
    cv[4::8] = bxs + bar_w;  cv[5::8] = by2_all
    cv[6::8] = bxs;          cv[7::8] = by2_all
    glColor4f(*th["wave_inner"], 0.70); _va_draw(cv, GL_QUADS)

    # Bright caps — only bars above threshold, one QUADS call
    cap_mask = mags > 0.02
    if np.any(cap_mask):
        ci = np.where(cap_mask)[0]
        kv = np.empty(len(ci) * 8, dtype=np.float32)
        kv[0::8] = bxs[ci];          kv[1::8] = by2_all[ci] - 0.5
        kv[2::8] = bxs[ci] + bar_w;  kv[3::8] = by2_all[ci] - 0.5
        kv[4::8] = bxs[ci] + bar_w;  kv[5::8] = by2_all[ci]
        kv[6::8] = bxs[ci];          kv[7::8] = by2_all[ci]
        glColor4f(*th["wave_core"], 0.90); _va_draw(kv, GL_QUADS)

    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)


def draw_waveform_lissajous(samples_l: np.ndarray, samples_r: np.ndarray,
                             rms: float, appst: AppState) -> None:
    """
    XY (Lissajous) scope — left channel → X axis, right channel → Y axis.
    Produces classic Lissajous figures for music; a diagonal line for mono.
    Same 4-pass additive bloom as the oscilloscope.

    Uses a stride so that the plotted points match NUM_POINTS regardless of
    input length, keeping the vertex buffer pre-allocated size consistent.
    """
    th   = appst.theme
    gain = appst.gain * (1.0 + rms * 1.8)

    cx = (BOX_L + BOX_R) / 2.0
    cy = CENTER_Y
    rx = (BOX_R - BOX_L) / 2.0 * 0.88
    ry = (BOX_T - BOX_B) / 2.0 * 0.88

    xs = np.clip(cx + samples_l * gain * rx, BOX_L + 0.5, BOX_R - 0.5).astype(np.float32)
    ys = np.clip(cy + samples_r * gain * ry, BOX_B + 0.5, BOX_T - 0.5).astype(np.float32)

    # Build flat vertex array [x0,y0, x1,y1, ...]
    verts = np.empty(NUM_POINTS * 2, dtype=np.float32)
    verts[0::2] = xs
    verts[1::2] = ys

    # Cross-hair reference axes (very faint)
    glColor4f(*th["grid"], 0.30); glLineWidth(0.6)
    glBegin(GL_LINES)
    glVertex2f(cx, BOX_B); glVertex2f(cx, BOX_T)
    glVertex2f(BOX_L, cy); glVertex2f(BOX_R, cy)
    glEnd()

    # 4-pass bloom — identical alphas/widths to oscilloscope for consistency
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    for width, color, alpha in (
        (7.0, th["wave_outer"], 0.045),
        (4.5, th["wave_mid"],   0.130),
        (2.5, th["wave_inner"], 0.400),
        (1.2, th["wave_core"],  0.900),
    ):
        glLineWidth(width)
        glColor4f(*color, alpha)
        _va_draw(verts, GL_LINE_STRIP, NUM_POINTS)

    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLineWidth(1.0)


def draw_scanning_eye(bounce_x: float, rms: float,
                      t: float, appst: AppState) -> None:
    ey      = SCR_B + 7.0
    r_outer = 3.2
    r_lens  = 2.2
    r_iris  = min(1.4 + rms * 0.9, r_lens * 0.92)
    th      = appst.theme

    glColor3f(*C_STEEL_MID);  filled_circle(bounce_x, ey, r_outer)
    glColor3f(*C_STEEL_LITE); glLineWidth(2.0)
    outline_circle(bounce_x, ey, r_outer)

    # Bevel arc — 9 pts, pre-computed with numpy
    arc_t  = np.linspace(math.pi*0.55, math.pi*(0.55+0.45), 9, dtype=np.float32)
    arc_v  = np.empty(18, dtype=np.float32)
    arc_v[0::2] = bounce_x + r_outer*0.87*np.cos(arc_t)
    arc_v[1::2] = ey       + r_outer*0.87*np.sin(arc_t)
    glColor4f(*C_STEEL_HI, 0.68); glLineWidth(2.8)
    _va_draw(arc_v, GL_LINE_STRIP, 9)

    glColor3f(0.01, 0.01, 0.01); filled_circle(bounce_x, ey, r_lens)

    pulse = 0.7 + 0.3 * math.sin(t * 3.6) + rms * 1.4
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glColor4f(*th["eye_iris"], min(pulse * 0.82, 1.0))
    filled_circle(bounce_x, ey, r_iris)
    glColor4f(*th["eye_hot"], min(pulse * 0.48, 0.80))
    filled_circle(bounce_x, ey, r_iris * 0.60)
    glColor4f(1.0, 1.0, 0.9, min(pulse * 0.30, 0.65))
    filled_circle(bounce_x, ey, r_iris * 0.28)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glColor4f(0, 0, 0, 0.78)
    filled_rect(bounce_x - r_iris*0.17, ey - r_iris*0.90,
                bounce_x + r_iris*0.17, ey + r_iris*0.90)

    glColor4f(1, 1, 1, 0.44); filled_circle(bounce_x - r_lens*0.36, ey + r_lens*0.40, r_lens*0.21)
    glColor4f(1, 1, 1, 0.20); filled_circle(bounce_x - r_lens*0.54, ey + r_lens*0.56, r_lens*0.10)

    # Cardinal lines — 4 line segments, one batch
    card_t  = np.array([0.0, math.pi/2, math.pi, 3*math.pi/2], dtype=np.float32)
    cos4, sin4 = np.cos(card_t), np.sin(card_t)
    cv = np.empty(16, dtype=np.float32)
    cv[0::4] = bounce_x + (r_outer+0.3)*cos4
    cv[1::4] = ey       + (r_outer+0.3)*sin4
    cv[2::4] = bounce_x + (r_outer+1.8)*cos4
    cv[3::4] = ey       + (r_outer+1.8)*sin4
    # Interleave into start/end pairs for GL_LINES
    lines_v = cv.reshape(4, 4)[:, [0,1,2,3]].flatten()
    glColor4f(*C_GOLD, 0.55); glLineWidth(1.0)
    _va_draw(lines_v, GL_LINES, 8)


# ═══════════════════════════════════════════════════════════════
# PANEL DRAW ROUTINES
# ═══════════════════════════════════════════════════════════════

def draw_top_banner(appst: AppState, rms: float, t: float) -> None:
    draw_steel_panel(0, BAN_B, W, H, raised=True)
    glColor3f(0.038, 0.033, 0.028)
    filled_rect(1.5, BAN_B+0.8, W-1.5, H-0.8)
    glColor3f(*C_GOLD); glLineWidth(1.4)
    glBegin(GL_LINES)
    glVertex2f(1.5, BAN_B+0.8); glVertex2f(W-1.5, BAN_B+0.8)
    glVertex2f(1.5, H-0.8);     glVertex2f(W-1.5, H-0.8)
    glEnd(); glLineWidth(1.0)

    mid_y = (BAN_B + H) / 2
    draw_text(f"⚙  {appst.unit_name}  ⚙", W/2, mid_y+0.9, size=22, color=(200,158,38))
    draw_text("RESONANCE VISUALIZER  •  SENSOR STREAM ACTIVE",
              W/2, mid_y-1.6, size=13, color=(118,96,28))

    lamp_cfg = [
        (7.5,    "SYS",  True,       (0.10, 0.90, 0.15), (0.04, 0.28, 0.04), 0.0),
        (15.5,   "PWR",  True,       (0.10, 0.90, 0.15), (0.04, 0.28, 0.04), 1.1),
        (23.5,   "COMM", True,       (0.10, 0.90, 0.15), (0.04, 0.28, 0.04), 2.3),
        (W-7.5,  "AMMO", True,       (0.95, 0.65, 0.05), (0.30, 0.20, 0.01), 0.7),
        (W-15.5, "SHLD", rms<0.45,   (0.10, 0.90, 0.15), (0.85, 0.03, 0.03), 1.9),
        (W-23.5, "TRGT", False,      (0.90, 0.03, 0.03), (0.25, 0.01, 0.01), 3.1),
    ]
    for lx, _lbl, lit, c_on, c_off, ph in lamp_cfg:
        draw_warning_lamp(lx, mid_y, lit, rms if lit else 0, t, ph, c_on, c_off)


def draw_bottom_status(appst: AppState, rms: float,
                       peak: float, frame: int) -> None:
    draw_steel_panel(0, 0, W, STAT_T, raised=True)
    glColor3f(0.038, 0.033, 0.028)
    filled_rect(1.5, 0.8, W-1.5, STAT_T-0.8)
    glColor3f(*C_GOLD); glLineWidth(1.1)
    glBegin(GL_LINES)
    glVertex2f(1.5, STAT_T-0.8); glVertex2f(W-1.5, STAT_T-0.8)
    glEnd(); glLineWidth(1.0)

    th = appst.theme
    bx1, bx2 = 52.0, 94.0
    by1, by2 = 1.5, STAT_T - 1.5
    glColor3f(*C_STEEL_DARK); filled_rect(bx1, by1, bx2, by2)
    lvl = min(rms * 8.0 * appst.gain, 1.0)
    bw  = (bx2 - bx1) * lvl
    bc  = (th["gauge_hi"] if lvl > 0.80 else
           th["gauge_mid"] if lvl > 0.50 else th["gauge_lo"])
    glColor3f(*bc); filled_rect(bx1, by1, bx1+bw, by2)
    glColor3f(*C_STEEL_HI); line_rect(bx1, by1, bx2, by2)

    mid_y  = STAT_T / 2
    spirit = ("BERSERK" if rms > 0.25 else "RAGING" if rms > 0.12 else "NOMINAL")
    draw_text(f"ENGINE SOUL: {spirit}", 13.0, mid_y, size=13,
              color=(158, 128, 28), anchor="left")
    draw_text("SIGNAL LVL", (bx1+bx2)/2, mid_y+1.45, size=10, color=(98,80,18))
    draw_text(f"RMS {rms:.2f}   PEAK {peak:.2f}   GAIN ×{appst.gain:.1f}",
              (bx1+bx2)/2, mid_y-1.35, size=10, color=(88,72,16))
    fps_col = (180, 60, 30) if appst.fps_actual < appst.fps_target * 0.85 else (158, 128, 28)
    draw_text(f"{appst.fps_actual:.0f}/{appst.fps_target} FPS",
              W-4.0, mid_y, size=13, color=fps_col, anchor="right")
    vsync_str = "VSY" if appst.vsync else "---"
    bwait_str = "BWA" if appst.busy_wait else "---"
    pers_str  = f"P{appst.persistence:02d}" if appst.persistence > 0 else "---"
    draw_text(f"[{THEME_ORDER[appst.theme_idx].upper()[:6]}] "
              f"[{appst.waveform[:3].upper()}] "
              f"[{'SCN' if appst.scanlines else '---'}] "
              f"[{'GRD' if appst.grid else '---'}] "
              f"[{pers_str}] [{vsync_str}] [{bwait_str}]",
              W/2, mid_y-3.2, size=9, color=(70,58,14))


def draw_gauge_panel(x1, x2, appst: AppState,
                     level: float, peak_hold: float,
                     skull_label: str) -> None:
    draw_steel_panel(x1, STAT_T, x2, BAN_B, raised=False)
    cx = (x1 + x2) / 2
    draw_skull(cx, BAN_B - 7.5, 4.0)
    draw_text(skull_label, cx, BAN_B-14.8, size=11, color=(138,108,22))

    gx1, gx2 = x1+4.0, x2-4.0
    gy1, gy2 = STAT_T+2.0, BAN_B-16.5
    draw_steel_panel(gx1-1, gy1-1, gx2+1, gy2+1, raised=False)
    draw_vertical_gauge(gx1, gy1, gx2, gy2, level, peak_hold, appst.theme)

    draw_iron_vow_seal(x1+4.0, STAT_T+10.0)
    draw_iron_vow_seal(x2-4.0, STAT_T+10.0)
    draw_rivet_col(x1+1.2, STAT_T+1, BAN_B-1, 4.0)
    draw_rivet_col(x2-1.2, STAT_T+1, BAN_B-1, 4.0)


def draw_main_screen_frame(appst: AppState, rms: float, t: float) -> None:
    draw_steel_panel(SCR_L, STAT_T, SCR_R, BAN_B, raised=False)
    draw_steel_panel(BOX_L-2, BOX_B-2, BOX_R+2, BOX_T+2, raised=False)

    glColor3f(*C_GOLD); glLineWidth(1.4)
    line_rect(BOX_L-1, BOX_B-1, BOX_R+1, BOX_T+1)
    glLineWidth(1.0)

    draw_gothic_arch((BOX_L+BOX_R)/2, BOX_T+1, BAN_B-0.5, (BOX_R-BOX_L)*0.38)

    for ox, oy in [(SCR_L+1.8, STAT_T+1.8), (SCR_R-1.8, STAT_T+1.8)]:
        glColor3f(*C_GOLD_DARK); sz = 1.8
        glBegin(GL_LINES)
        glVertex2f(ox-sz,oy); glVertex2f(ox+sz,oy)
        glVertex2f(ox,oy-sz); glVertex2f(ox,oy+sz)
        glEnd()
        draw_rivet(ox, oy, 0.70)

    lit_col = appst.theme["eye_iris"]
    draw_warning_lamp(BOX_L+1.8, BOX_T+3.5, True, rms, t, 0.0,    lit_col, (0.1,0,0))
    draw_warning_lamp(BOX_R-1.8, BOX_T+3.5, True, rms, t, math.pi, lit_col, (0.1,0,0))

    draw_rivet_row(SCR_L+1.5, SCR_R-1.5, BAN_B-1.5, 4.5)
    draw_rivet_row(SCR_L+1.5, SCR_R-1.5, STAT_T+1.5, 4.5)

    draw_text("OPTICAL SENSOR UNIT Ω-VII",
              (BOX_L+BOX_R)/2, SCR_B+1.8, size=10, color=(88,72,16))
    draw_text(f"MODE: {appst.waveform.upper()}",
              BOX_R-1.0, BOX_T+1.2, size=9, color=(100,82,18), anchor="right")


def draw_help_overlay() -> None:
    glColor4f(0.03, 0.02, 0.01, 0.90)
    filled_rect(16, 6, 114, 64)
    glColor3f(*C_GOLD); glLineWidth(1.5)
    line_rect(16, 6, 114, 64)
    glLineWidth(1.0)
    draw_text("COGITATION CORE — HOTKEYS", 65, 61, size=16, color=(200,158,38))
    lines = [
        ("T",      "Cycle colour theme:"),
        ("",       "iron · void · plague · gold · chaos · frost · lava"),
        ("",       "bone · nuclear · midnight · phosphor · ember · mercury"),
        ("",       "plasma · abyss · rust"),
        ("B",      "Waveform: oscilloscope / spectrum / both / lissajous"),
        ("P",      "Persistence trail: 0 → 4 → 8 → 16 frames"),
        ("G",      "Toggle grid"),
        ("S",      "Toggle CRT scanlines"),
        ("F",      "Toggle fullscreen"),
        ("+ / -",  "Adjust input gain"),
        ("H",      "Close this panel"),
        ("Escape", "Quit"),
    ]
    for i, (key, desc) in enumerate(lines):
        y = 57.5 - i * 4.4
        if key:
            draw_text(f"{key:<8}", 22, y, size=11, color=(200,158,38), anchor="left")
        draw_text(desc, 44, y, size=11, color=(160,130,58), anchor="left")


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════
def main() -> None:
    global _current_width, _current_height

    args  = parse_args()
    appst = AppState(args)
    audio = AudioState()

    try:
        jclient = create_jack_client(audio)
    except RuntimeError as exc:
        print(f"ERROR: {exc}"); sys.exit(1)

    pygame.init()
    _current_width, _current_height = args.width, args.height

    # ── VSync: set SDL swap control before creating the GL context ────────────
    if args.vsync:
        # Adaptive vsync (-1) falls back to regular vsync if unsupported
        pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, -1)
        if pygame.display.gl_get_attribute(pygame.GL_SWAP_CONTROL) == 0:
            pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)
        print("ℹ  VSync enabled.")

    # ── Window flags ─────────────────────────────────────────────────────────
    flags = DOUBLEBUF | OPENGL | RESIZABLE
    if args.borderless:
        flags |= pygame.NOFRAME
        print("ℹ  Borderless mode active.")

    pygame.display.set_mode((args.width, args.height), flags)
    pygame.display.set_caption(
        f"{appst.unit_name}  •  RESONANCE VISUALIZER  •  STREAM ACTIVE")

    glClearColor(*C_STEEL_BG, 1.0)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_LINE_SMOOTH)
    glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    def _set_viewport(w: int, h: int) -> None:
        global _current_width, _current_height
        _current_width, _current_height = w, h
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        glOrtho(0, W, 0, H, -1, 1)
        glMatrixMode(GL_MODELVIEW)

    _set_viewport(args.width, args.height)

    sine_phase  = 0.0
    bounce_x    = (BOX_L + BOX_R) / 2
    bounce_dir  = 1.0
    ph_left     = 0.0
    ph_right    = 0.0
    frame_count = 0
    prev_time   = time.monotonic()
    clock       = pygame.time.Clock()

    # FPS rolling average (last 30 frame durations)
    _frame_times: deque = deque(maxlen=30)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                _set_viewport(event.w, event.h)
            elif event.type == KEYDOWN:
                if   event.key == K_ESCAPE:                        running = False
                elif event.key == K_t:                             appst.cycle_theme()
                elif event.key == K_b:                             appst.cycle_waveform()
                elif event.key == K_g:                             appst.grid      ^= True
                elif event.key == K_s:                             appst.scanlines ^= True
                elif event.key == K_h:                             appst.show_help ^= True
                elif event.key == K_p:                             appst.cycle_persistence()
                elif event.key in (K_PLUS, K_EQUALS, K_KP_PLUS):  appst.nudge_gain(+0.1)
                elif event.key in (K_MINUS, K_KP_MINUS):           appst.nudge_gain(-0.1)
                elif event.key == K_f:
                    appst.fullscreen ^= True
                    f2 = flags | (pygame.FULLSCREEN if appst.fullscreen else 0)
                    pygame.display.set_mode((args.width, args.height), f2)
                    _set_viewport(args.width, args.height)

        now       = time.monotonic()
        dt        = min(now - prev_time, 0.1)
        prev_time = now
        t         = now

        # Rolling FPS measurement
        _frame_times.append(dt)
        if len(_frame_times) >= 2:
            appst.fps_actual = 1.0 / (sum(_frame_times) / len(_frame_times))

        # Advance theme lerp
        appst.advance_lerp(dt)

        samples, rms, peak = audio.snapshot()
        if appst.waveform == "lissajous":
            samples_l, samples_r, rms, peak = audio.snapshot_stereo()
        else:
            samples_l = samples_r = samples

        # Beat flash trigger and decay
        if audio.beat_detected:
            appst.beat_flash = 1.0
        else:
            appst.beat_flash = max(0.0, appst.beat_flash - dt * 6.5)

        sine_phase += SINE_SPEED * dt
        speed       = EYE_SPEED + rms * 22.0
        bounce_x   += bounce_dir * speed * dt
        if   bounce_x >= BOX_R - 8.0: bounce_x = BOX_R - 8.0; bounce_dir = -1.0
        elif bounce_x <= BOX_L + 8.0: bounce_x = BOX_L + 8.0; bounce_dir =  1.0

        ph_left  = max(min(rms  * 8.0 * appst.gain, 1.0), ph_left  - 0.28*dt)
        ph_right = max(min(peak * 4.0 * appst.gain, 1.0), ph_right - 0.28*dt)

        # ── Render ───────────────────────────────────────────────────────────
        glClear(GL_COLOR_BUFFER_BIT)
        glColor3f(*C_STEEL_BG); filled_rect(0, 0, W, H)

        draw_top_banner(appst, rms, t)
        draw_bottom_status(appst, rms, peak, frame_count)
        draw_gauge_panel(GAU_L,  GAU_R,  appst,
                         min(rms*8.0*appst.gain,  1.0), ph_left,  "SIGNAL LVL")
        draw_gauge_panel(GAU2_L, GAU2_R, appst,
                         min(peak*4.0*appst.gain, 1.0), ph_right, "PEAK HOLD")
        draw_main_screen_frame(appst, rms, t)
        draw_screen_bg(appst)

        if appst.waveform in ("oscilloscope", "both"):
            draw_waveform_oscilloscope(samples_l, rms, sine_phase, appst)
        if appst.waveform in ("spectrum", "both"):
            draw_waveform_spectrum(samples_l, rms, appst)
        if appst.waveform == "lissajous":
            draw_waveform_lissajous(samples_l, samples_r, rms, appst)

        draw_scanning_eye(bounce_x, rms, t, appst)

        if appst.show_help:
            draw_help_overlay()

        frame_count += 1
        pygame.display.flip()

        # ── Frame rate control ────────────────────────────────────────────────
        # VSync: SDL handles pacing; we still cap to avoid hammering the GPU
        # on systems where vsync swap isn't rate-limiting.
        # busy_wait: clock.tick_busy_loop gives sub-millisecond accuracy at
        # the cost of 100% CPU on one core during the wait window.
        if not args.vsync:
            if args.busy_wait:
                clock.tick_busy_loop(args.fps)
            else:
                clock.tick(args.fps)
        else:
            # With vsync active just call tick with a generous ceiling so we
            # still accumulate timing data without spinning.
            clock.tick(args.fps * 2)

    if jclient:
        jclient.deactivate(); jclient.close()
    for tid, _, _ in _tex_lru.values():
        glDeleteTextures([tid])
    pygame.quit()


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   IRON SEPULCHRE WALKER Mk.IV  •  RESONANCE VISUALIZER v2.4 ║")
    print("║           MOTIVE ANIMUS AWAKENING...  BY IRON AND WILL       ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  16 Themes: iron · void · plague · gold · chaos · frost      ║")
    print("║             lava · bone · nuclear · midnight · phosphor       ║")
    print("║             ember · mercury · plasma · abyss · rust           ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Modes:  oscilloscope  spectrum  both  lissajous(XY)         ║")
    print("║  Flags:  --vsync  --borderless  --busy-wait  --fps N         ║")
    print("║          --persistence N  --theme NAME  --gain X             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("  Press H in-app for hotkey reference.")
    main()
