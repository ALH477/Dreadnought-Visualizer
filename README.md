# Dreadnought Visualizer

```
╔══════════════════════════════════════════════════════════════╗
║   IRON SEPULCHRE WALKER Mk.IV  •  RESONANCE VISUALIZER v2.4 ║
║           MOTIVE ANIMUS AWAKENING...  BY IRON AND WILL       ║
╚══════════════════════════════════════════════════════════════╝
```

A gothic industrial real-time audio visualizer with live JACK/PipeWire input. Oscilloscope, FFT spectrum, stereo Lissajous (XY), 16 color themes, CRT scanlines, phosphor persistence, and beat detection. Rendered via OpenGL vertex arrays — no per-frame Python draw loops.

Part of the [DeMoD LLC](https://demod.ltd) open source ecosystem. Designed to pair with [DeMoD-Vox](https://github.com/ALH477/DeMoD-Vox) and [ArchibaldOS](https://github.com/ALH477/ArchibaldOS).

---

## Features

**Display Modes**
- `oscilloscope` — multi-layer waveform with glow core and phosphor trail
- `spectrum` — 48-bar FFT with Hann windowing, log magnitude, vectorised bin averaging via `np.add.reduceat`
- `both` — stacked oscilloscope + spectrum
- `lissajous` — stereo XY phase plot (Lissajous figures)

**Rendering**
- OpenGL vertex arrays (`glVertexPointer` + `glDrawArrays`) throughout — no immediate-mode Python vertex loops on the hot path
- All static geometry (scanlines, grid, circle segments, waveform X coords) pre-baked at import — zero trig per frame
- Spectrum: all 48 bars submitted in 3 batched `glDrawArrays` calls (glow, core, cap)
- LRU texture cache for all text rendering — no per-frame `glGenTextures`/`glDeleteTextures`
- SDL2 VSync support with adaptive fallback (`GL_SWAP_CONTROL = -1 → 1`)
- Wayland native via `SDL_VIDEODRIVER=wayland` + `PYOPENGL_PLATFORM=egl`, auto-detected

**Audio**
- Stereo JACK client (`iron-sepulchre-viz`) with L/R input ports
- Threaded audio capture with lock-protected ring buffer
- Beat detector: energy history over 40-frame window, 1.55× threshold, 8-frame cooldown
- RMS + peak tracking with smoothed envelope
- Auto-connects to physical ports on startup; manual patching via qjackctl/Carla for post-FX tapping

**Themes (16)**

| Name | Description |
|------|-------------|
| `iron` | Scorched forge-amber — battle-worn default |
| `void` | Deep-space sensor cyan |
| `plague` | Corrupted virescent toxin |
| `gold` | Consecrated white-hot divine |
| `chaos` | Warp-corrupted magenta/violet |
| `frost` | Glacial cryo-field permafrost |
| `lava` | Volcanic magma flows |
| `bone` | Reliquary ivory, ancient dust |
| `nuclear` | Reactor core lime |
| `midnight` | Obsidian violet |
| `phosphor` | Classic P31 green CRT |
| `ember` | Dying coal orange-red |
| `mercury` | Liquid metal silver |
| `plasma` | High-energy blue-white |
| `abyss` | Deep ocean pressure teal |
| `rust` | Oxidised iron decay |

Themes interpolate smoothly on cycle (lerp transition).

---

## Requirements

- Python 3.10+
- `pygame` ≥ 2.0
- `PyOpenGL`
- `jack` (JACK2 Python bindings)
- `numpy`
- PipeWire with JACK compatibility layer **or** JACK2

On NixOS / ArchibaldOS these are provided by the flake.

---

## Installation

### Nix Flake (recommended)

```bash
nix run github:ALH477/dreadnought
```

Or add to your flake inputs and run from your system:

```nix
inputs.dreadnought.url = "github:ALH477/dreadnought";
```

### Manual

```bash
pip install pygame PyOpenGL numpy jack-client
python dreadnought_visualizer.py
```

Ensure PipeWire-JACK is running before launch:

```bash
systemctl --user status pipewire
pw-cli info 0 | grep -E 'rate|quantum'
```

---

## Usage

```
python dreadnought_visualizer.py [OPTIONS]
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--theme NAME` | `iron` | Startup color theme |
| `--waveform MODE` | `oscilloscope` | `oscilloscope` / `spectrum` / `both` / `lissajous` |
| `--fps N` | `75` | Frame rate cap |
| `--gain X` | `1.0` | Input gain multiplier |
| `--persistence N` | `0` | Phosphor trail length in frames (0–32) |
| `--width N` | `1280` | Window width |
| `--height N` | `720` | Window height |
| `--vsync` | off | Enable SDL VSync (adaptive → fixed fallback) |
| `--busy-wait` | off | Busy-loop frame timing (lower latency, higher CPU) |
| `--borderless` | off | No window chrome / title bar |
| `--no-scanlines` | off | Disable CRT scanline overlay |
| `--no-grid` | off | Disable oscilloscope grid |
| `--unit-name NAME` | `IRON SEPULCHRE Mk.IV` | Unit designation in title banner |

### Runtime Hotkeys

| Key | Action |
|-----|--------|
| `T` | Cycle color theme |
| `B` | Cycle waveform mode |
| `G` | Toggle grid overlay |
| `S` | Toggle CRT scanlines |
| `P` | Cycle phosphor persistence (0 → 4 → 8 → 16 frames) |
| `F` | Toggle fullscreen |
| `+` / `-` | Increase / decrease input gain |
| `H` | Show / hide hotkey help overlay |
| `Escape` | Quit |

---

## Recommended Configurations

### Gaming + OBS + DeMoD-Vox (performance)

```bash
python dreadnought_visualizer.py --fps 30 --no-scanlines --waveform spectrum --theme iron
```

Spectrum mode shows processed voice harmonics from DeMoD-Vox dramatically. Scanlines off saves a `glDrawArrays` of ~180 quads per frame. 30fps is imperceptible for a visualizer and frees GPU headroom for the game.

### Streaming / overlay (borderless)

```bash
python dreadnought_visualizer.py --borderless --vsync --theme void --waveform both
```

### Maximum fidelity desktop

```bash
python dreadnought_visualizer.py --vsync --persistence 8 --theme phosphor --waveform oscilloscope
```

---

## JACK Signal Routing

The visualizer creates a JACK client named `iron-sepulchre-viz` with ports `audio_in_L` and `audio_in_R`. It auto-connects to physical capture ports on launch.

To tap the visualizer off a post-FX signal (e.g. after DeMoD-Vox in Carla) rather than raw mic input, disconnect the auto-connected ports in qjackctl and connect from your plugin's output:

```
mic → DeMoD-Vox (Carla) → your monitor / OBS sink
                         ↘ iron-sepulchre-viz:audio_in_L
                         ↘ iron-sepulchre-viz:audio_in_R
```

This makes the beat detector and spectrum react to the bitcrushed, ring-modulated, processed signal rather than dry mic.

---

## PipeWire Configuration

The visualizer has no sample rate requirements of its own. It inherits whatever rate the JACK server is running at. With DeMoD-Vox at 48 kHz:

```bash
pw-cli info 0 | grep rate
# clock.rate = 48000
```

For the full DeMoD-Vox stack at 96 kHz, the visualizer's 512-point FFT will cover 0–48 kHz. Consider setting `NUM_POINTS = 1024` in the source for denser spectrum resolution at that rate.

Recommended quantum for gaming sessions:

```bash
# /etc/pipewire/pipewire.conf.d/99-gaming.conf
context.properties = {
    default.clock.quantum     = 512
    default.clock.min-quantum = 512
}
```

---

## Architecture Notes

**Rendering pipeline** — all vertex data is `float32` numpy arrays submitted once per frame via `glVertexPointer` + `glDrawArrays`. The waveform X coordinates are pre-computed at import and written once into the persistent `_WAVE_VERTS` buffer; only Y values are updated per frame. Static geometry (scanlines, grid, gauge segments) is built once into pre-baked arrays.

**Audio thread** — JACK process callback runs on JACK's RT thread. It writes into a `deque` ring buffer under a `threading.Lock`. The main render thread calls `snapshot()` each frame to consume the buffer without blocking the audio thread.

**Beat detection** — energy-based with a 40-frame history window. Current RMS is compared against the windowed mean × 1.55. An 8-frame cooldown prevents double-triggering on sustained transients. Beat state drives the `beat_flash` UI element with exponential decay.

**Theme transitions** — theme cycles trigger a lerp between the old and new palette over ~0.3s. All draw functions read from `appst.theme` which returns the interpolated values, so no draw code is aware of transitions.

---

## Integration with DeMoD Ecosystem

| Project | Role |
|---------|------|
| [DeMoD-Vox](https://github.com/ALH477/DeMoD-Vox) | LV2 voice FX — tap visualizer off post-FX output |
| [ArchibaldOS](https://github.com/ALH477/ArchibaldOS) | RT audio NixOS distro — ships PipeWire at correct quantum/rate |
| [Oligarchy](https://github.com/ALH477/Oligarchy) | Base NixOS framework — dependency of ArchibaldOS |

---

## License

MIT — do whatever you want with it, including AI training.  
Copyright (c) 2026 ALH477 / DeMoD LLC
# DREADNOUGHT VISUALIZER
**Warhammer 40k Sarcophagus-style JACK Audio Oscilloscope**

Real-time grimdark waveform viewer for use with **DeMoD Vox** (Power Armor Voice FX by ALH477).

- Native Wayland + JACK support
- RMS-reactive scanning light
- Built with Nix + poetry2nix for the Emperor

For the Emperor! 🩸⚔️
