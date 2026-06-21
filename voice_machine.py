import sys
import customtkinter as ctk
import subprocess
import threading
import os
import re
import wave
import winsound
import time
import tempfile
import tkinter as tk
import numpy as np

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# PyInstaller-compatible base path
if getattr(sys, "frozen", False):
    _HERE = os.path.dirname(sys.executable)
    # PyInstaller temp extraction folder
    _TMPDIR = sys._MEIPASS
else:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _TMPDIR = _HERE

SAM_DIR    = os.path.join(_TMPDIR, "SAM")
SAM_EXE    = os.path.join(SAM_DIR, "sam.exe")
PIPER_DIR  = os.path.join(_TMPDIR, "piper", "piper")
PIPER_EXE  = os.path.join(PIPER_DIR, "piper.exe")
VOICES_DIR = os.path.join(_TMPDIR, "piper", "voices")
_ICON      = os.path.join(_HERE, "start.ico")
_TMPWAV    = os.path.join(tempfile.gettempdir(), "khold_vm_out.wav")

# Add SAM directory to PATH so SDL.dll is found
if SAM_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = SAM_DIR + os.pathsep + os.environ.get("PATH", "")

# ── SAM character presets ────────────────────────────────────────────────────
# Speed/Pitch stored as slider display values (higher = faster/higher pitch).
# IntVars store SAM values = 255 - slider_val; _play uses them directly.
# Tongue (throat) and Nose (mouth) are direct SAM values — no inversion.
# name, slider_speed, slider_pitch, tongue, nose
PRESETS = [
    ("SAM",             183, 191, 128, 128),
    ("Elf",             183, 191, 110, 160),
    ("Stuffy Guy",      173, 183, 110, 105),
    ("Little Old Lady", 183, 223, 145, 145),
    ("Alien",           213, 195, 190, 190),
    ("E.T.",            135, 197, 200, 150),
    ("Deep Voice",      183,  86, 128, 128),
    ("High Voice",      183, 225, 128, 128),
    ("Grandma",         183, 215, 135, 145),
    ("Speed Demon",     225, 191, 128, 128),
]

SAM_COLORS = [
    "#E74C3C", "#E67E22", "#F39C12", "#27AE60", "#2980B9",
    "#8E44AD", "#E91E63", "#16A085", "#2C3E50", "#D35400",
]

# ── Piper natural voices ─────────────────────────────────────────────────────
# name, accent label, onnx filename
NAT_VOICES = [
    ("Ryan",   "US Male",        "en_US-ryan-medium.onnx"),
    ("Lessac", "US Female",      "en_US-lessac-medium.onnx"),
    ("Cori",   "UK Female",      "en_GB-cori-medium.onnx"),
    ("Alan",   "UK Male (Deep)", "en_GB-alan-medium.onnx"),
    ("Joe",    "US Male",        "en_US-joe-medium.onnx"),
    ("Amy",    "US Female",      "en_US-amy-medium.onnx"),
]
NAT_COLORS = ["#2980B9", "#8E44AD", "#16A085", "#C0392B", "#E67E22", "#1ABC9C"]

_LOOP_OFF = "#95A5A6"
_LOOP_ON  = "#E67E22"
_MODE_OFF = "#BDC3C7"
_LIVE_ON  = "#3498DB"
_SING_ON  = "#9B59B6"

# Pentatonic scale in SAM pitch values (lower SAM value = higher frequency)
SING_SCALE = [105, 94, 84, 75, 67, 75, 84, 94]

_SMOOTH = np.array([0.25, 0.5, 0.25], dtype=np.float32)


def _apply_tremolo(sig, sample_rate, rate=5.0, depth=0.6):
    t   = np.arange(len(sig), dtype=np.float32) / sample_rate
    lfo = 1.0 - (depth / 2.0) * (1.0 - np.cos(2.0 * np.pi * rate * t))
    return sig * lfo


def _process_wav(path, volume, sing=False):
    """Volume + lowpass (+ optional tremolo) in-place. Handles 8-bit SAM and 16-bit Piper."""
    with wave.open(path, "rb") as wf:
        params = wf.getparams()
        raw    = wf.readframes(params.nframes)
    sr = params.framerate
    if params.sampwidth == 1:                               # 8-bit unsigned (SAM)
        sig = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0
        sig *= volume
        sig  = np.convolve(sig, _SMOOTH, mode="same")
        if sing:
            sig = _apply_tremolo(sig, sr)
        out  = np.clip(sig + 128.0, 0, 255).astype(np.uint8)
    else:                                                   # 16-bit signed (Piper)
        sig = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        sig *= volume
        sig  = np.convolve(sig, _SMOOTH, mode="same")
        if sing:
            sig = _apply_tremolo(sig, sr)
        out  = np.clip(sig, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(out.tobytes())


def _concat_wavs(paths, out_path):
    """Concatenate WAV files into out_path (all must share the same format)."""
    frames = b""
    params = None
    for p in paths:
        try:
            with wave.open(p, "rb") as wf:
                if params is None:
                    params = wf.getparams()
                frames += wf.readframes(wf.getnframes())
        except Exception:
            pass
    if params and frames:
        with wave.open(out_path, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames)


class VoiceMachine(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Khold Voices")
        self.geometry("900x860")
        self.minsize(780, 700)
        self.resizable(True, True)

        if os.path.exists(_ICON):
            self.iconbitmap(_ICON)

        self.configure(fg_color="#FFF8E7")

        self._looping      = False
        self._singing      = False
        self._live_mode    = False
        self._live_after   = None          # pending after() id for live word
        self._stop_evt     = threading.Event()
        self._play_gen     = 0
        self._vol          = 0.8

        self._selected = 0
        self._speed    = tk.IntVar(value=PRESETS[0][1])
        self._pitch    = tk.IntVar(value=PRESETS[0][2])
        self._tongue   = tk.IntVar(value=PRESETS[0][3])
        self._nose     = tk.IntVar(value=PRESETS[0][4])
        self._sl = {}
        self._ll = {}

        self._nat_sel   = 0
        self._nat_speed = 100

        self._build()
        self._select(0)
        self._select_nat(0)

        # Maximize after the window is fully built
        self.after(50, lambda: self.state("zoomed"))

    # ─────────────────────────────────────────────────────────────── build ──

    def _build(self):
        ctk.CTkLabel(self, text="Khold Voices",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#2C3E50").pack(pady=(14, 2))
        ctk.CTkLabel(self, text="Type something, pick a voice, and hit PLAY!",
                     font=ctk.CTkFont(size=14), text_color="#7F8C8D").pack(pady=(0, 6))

        # text input
        tf = ctk.CTkFrame(self, fg_color="transparent")
        tf.pack(padx=30, fill="both", expand=True)
        ctk.CTkLabel(tf, text="What should I say?",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#2C3E50", anchor="w").pack(fill="x", pady=(0, 4))
        self._txt = ctk.CTkTextbox(tf, height=60, font=ctk.CTkFont(size=16),
                                   fg_color="white", border_color="#BDC3C7",
                                   border_width=2, corner_radius=10)
        self._txt.pack(fill="both", expand=True)
        self._txt.insert("1.0", "Hello! I am Khold Voices!")
        self._txt.bind("<KeyRelease>", self._on_keyrelease)

        # tabs
        self._tabs = ctk.CTkTabview(
            self, fg_color="#FFF8E7",
            segmented_button_selected_color="#2C3E50",
            segmented_button_selected_hover_color="#3D566E",
            segmented_button_unselected_color="#ECF0F1",
            text_color="white", text_color_disabled="#7F8C8D")
        self._tabs.pack(padx=30, pady=(6, 0), fill="both", expand=True)
        self._tabs.add("🤖  Character Voices")
        self._tabs.add("🎤  Natural Voices")
        self._tabs.set("🤖  Character Voices")
        self._build_character_tab()
        self._build_natural_tab()

        # volume
        vf   = ctk.CTkFrame(self, fg_color="#ECF0F1", corner_radius=12)
        vf.pack(padx=30, pady=(6, 0), fill="x")
        vrow = ctk.CTkFrame(vf, fg_color="transparent")
        vrow.pack(padx=16, pady=7, fill="x")
        ctk.CTkLabel(vrow, text="Volume", width=68, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#2C3E50").pack(side="left")
        self._vol_lbl = ctk.CTkLabel(vrow, text="80%", width=36, anchor="e",
                                     font=ctk.CTkFont(size=13), text_color="#555555")
        self._vol_lbl.pack(side="right")
        def on_vol(v):
            self._vol = int(round(v)) / 100.0
            self._vol_lbl.configure(text=f"{int(round(v))}%")
        vs = ctk.CTkSlider(vrow, from_=0, to=100, number_of_steps=100,
                           progress_color="#3498DB", command=on_vol)
        vs.set(80)
        vs.pack(side="left", fill="x", expand=True, padx=(8, 8))

        # mode toggles (LIVE + SING)
        mf = ctk.CTkFrame(self, fg_color="transparent")
        mf.pack(padx=30, pady=(6, 0), fill="x")
        self._live_btn = ctk.CTkButton(
            mf, text="⌨️  LIVE", font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=_MODE_OFF, hover_color=self._dim(_MODE_OFF),
            height=40, corner_radius=10, command=self._toggle_live)
        self._live_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._sing_btn = ctk.CTkButton(
            mf, text="🎵  SING", font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=_MODE_OFF, hover_color=self._dim(_MODE_OFF),
            height=40, corner_radius=10, command=self._toggle_sing)
        self._sing_btn.pack(side="left", fill="x", expand=True)

        # play / loop / stop
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=30, pady=(6, 0), fill="x")
        self._play_btn = ctk.CTkButton(
            bf, text="▶  PLAY", font=ctk.CTkFont(size=21, weight="bold"),
            fg_color="#2ECC71", hover_color="#27AE60",
            height=56, corner_radius=14, command=self._play)
        self._play_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._loop_btn = ctk.CTkButton(
            bf, text="↺  LOOP", font=ctk.CTkFont(size=21, weight="bold"),
            fg_color=_LOOP_OFF, hover_color=self._dim(_LOOP_OFF),
            height=56, corner_radius=14, command=self._toggle_loop)
        self._loop_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._stop_btn = ctk.CTkButton(
            bf, text="■  STOP", font=ctk.CTkFont(size=21, weight="bold"),
            fg_color="#E74C3C", hover_color="#C0392B",
            height=56, corner_radius=14, state="disabled", command=self._stop)
        self._stop_btn.pack(side="left", fill="x", expand=True)

        self._status = ctk.CTkLabel(self, text="",
                                    font=ctk.CTkFont(size=13), text_color="#7F8C8D")
        self._status.pack(pady=(4, 8))

    # ── Character Voices tab ─────────────────────────────────────────────────

    def _build_character_tab(self):
        tab = self._tabs.tab("🤖  Character Voices")
        ctk.CTkLabel(tab, text="Choose a Voice:",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#2C3E50", anchor="w").pack(fill="x", pady=(4, 6))
        grid = ctk.CTkFrame(tab, fg_color="transparent")
        grid.pack(fill="x")
        self._btns = []
        for i, (name, *_) in enumerate(PRESETS):
            r, c = divmod(i, 5)
            color = SAM_COLORS[i]
            btn = ctk.CTkButton(grid, text=name,
                                font=ctk.CTkFont(size=13, weight="bold"),
                                fg_color=color, hover_color=self._dim(color),
                                text_color="white", corner_radius=10, height=40,
                                command=lambda i=i: self._select(i))
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            grid.columnconfigure(c, weight=1)
            self._btns.append(btn)

        sf = ctk.CTkFrame(tab, fg_color="#ECF0F1", corner_radius=12)
        sf.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(sf, text="Voice Settings",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#2C3E50").pack(anchor="w", padx=14, pady=(8, 3))
        sa = ctk.CTkFrame(sf, fg_color="transparent")
        sa.pack(padx=14, pady=(0, 8), fill="x")
        self._add_slider(sa, "Speed",  self._speed,  invert=True)
        self._add_slider(sa, "Pitch",  self._pitch,  invert=True)
        self._add_slider(sa, "Tongue", self._tongue)
        self._add_slider(sa, "Nose",   self._nose)

    def _add_slider(self, parent, label, var, invert=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=62, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#2C3E50").pack(side="left")
        lbl = ctk.CTkLabel(row, text=str(var.get()), width=36, anchor="e",
                           font=ctk.CTkFont(size=13), text_color="#555555")
        lbl.pack(side="right")
        def on_slide(v, _v=var, _l=lbl, _inv=invert):
            iv = int(round(v))
            _v.set(255 - iv if _inv else iv)
            _l.configure(text=str(iv))
        initial = (255 - var.get()) if invert else var.get()
        sl = ctk.CTkSlider(row, from_=0, to=255, number_of_steps=255, command=on_slide)
        sl.set(initial)
        sl.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self._sl[label] = sl
        self._ll[label] = lbl

    # ── Natural Voices tab ────────────────────────────────────────────────────

    def _build_natural_tab(self):
        tab = self._tabs.tab("🎤  Natural Voices")
        ctk.CTkLabel(tab, text="Choose a Voice:",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#2C3E50", anchor="w").pack(fill="x", pady=(4, 6))

        self._nat_btns = []
        btn_grid = ctk.CTkFrame(tab, fg_color="transparent")
        btn_grid.pack(fill="x")
        for i, (name, accent, _) in enumerate(NAT_VOICES):
            r, c = divmod(i, 3)
            color = NAT_COLORS[i]
            cell = ctk.CTkFrame(btn_grid, fg_color="transparent")
            cell.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            btn_grid.columnconfigure(c, weight=1)
            btn = ctk.CTkButton(cell, text=name,
                                font=ctk.CTkFont(size=15, weight="bold"),
                                fg_color=color, hover_color=self._dim(color),
                                text_color="white", corner_radius=12, height=50,
                                command=lambda i=i: self._select_nat(i))
            btn.pack(fill="x")
            ctk.CTkLabel(cell, text=accent,
                         font=ctk.CTkFont(size=10), text_color="#7F8C8D").pack(pady=(2, 0))
            self._nat_btns.append(btn)

        sf = ctk.CTkFrame(tab, fg_color="#ECF0F1", corner_radius=12)
        sf.pack(fill="x", pady=(10, 0))
        srow = ctk.CTkFrame(sf, fg_color="transparent")
        srow.pack(padx=14, pady=10, fill="x")
        ctk.CTkLabel(srow, text="Speed", width=62, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#2C3E50").pack(side="left")
        self._nat_spd_lbl = ctk.CTkLabel(srow, text="Normal", width=52, anchor="e",
                                         font=ctk.CTkFont(size=13), text_color="#555555")
        self._nat_spd_lbl.pack(side="right")
        def on_nat_speed(v):
            iv = int(round(v))
            self._nat_speed = iv
            self._nat_spd_lbl.configure(
                text="Slow" if iv < 80 else "Fast" if iv > 130 else "Normal")
        nat_sl = ctk.CTkSlider(srow, from_=50, to=200, number_of_steps=150,
                               command=on_nat_speed)
        nat_sl.set(100)
        nat_sl.pack(side="left", fill="x", expand=True, padx=(8, 8))

    # ──────────────────────────────────────────────────────────── helpers ──

    def _dim(self, c):
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        return f"#{int(r*.72):02x}{int(g*.72):02x}{int(b*.72):02x}"

    def _select(self, idx):
        self._selected = idx
        for i, btn in enumerate(self._btns):
            btn.configure(fg_color=SAM_COLORS[i], border_width=0)
        self._btns[idx].configure(border_width=3, border_color="white")
        _, spd, pitch, tongue, nose = PRESETS[idx]
        for label, var, val, inv in [("Speed",  self._speed,  spd,   True),
                                     ("Pitch",  self._pitch,  pitch, True),
                                     ("Tongue", self._tongue, tongue, False),
                                     ("Nose",   self._nose,   nose,  False)]:
            var.set(255 - val if inv else val)
            self._sl[label].set(val)
            self._ll[label].configure(text=str(val))

    def _select_nat(self, idx):
        self._nat_sel = idx
        for i, btn in enumerate(self._nat_btns):
            btn.configure(fg_color=NAT_COLORS[i], border_width=0)
        self._nat_btns[idx].configure(border_width=3, border_color="white")

    def _toggle_loop(self):
        self._looping = not self._looping
        if self._looping:
            self._loop_btn.configure(fg_color=_LOOP_ON,
                                     hover_color=self._dim(_LOOP_ON),
                                     text="↺  LOOP  ✓")
        else:
            self._loop_btn.configure(fg_color=_LOOP_OFF,
                                     hover_color=self._dim(_LOOP_OFF),
                                     text="↺  LOOP")

    def _toggle_live(self):
        self._live_mode = not self._live_mode
        if self._live_mode:
            self._live_btn.configure(fg_color=_LIVE_ON,
                                     hover_color=self._dim(_LIVE_ON),
                                     text="⌨️  LIVE  ✓")
            self._status.configure(text="Live mode: press Space after each word")
        else:
            self._live_btn.configure(fg_color=_MODE_OFF,
                                     hover_color=self._dim(_MODE_OFF),
                                     text="⌨️  LIVE")
            self._status.configure(text="")
            if self._live_after:
                self.after_cancel(self._live_after)
                self._live_after = None

    def _toggle_sing(self):
        self._singing = not self._singing
        if self._singing:
            self._sing_btn.configure(fg_color=_SING_ON,
                                     hover_color=self._dim(_SING_ON),
                                     text="🎵  SING  ✓")
        else:
            self._sing_btn.configure(fg_color=_MODE_OFF,
                                     hover_color=self._dim(_MODE_OFF),
                                     text="🎵  SING")

    # ──────────────────────────────────────────────── live (word-by-word) ──

    def _on_keyrelease(self, event):
        if not self._live_mode or event.keysym != "space":
            return
        words = self._txt.get("1.0", "end").split()
        if not words:
            return
        word = re.sub(r"[^\w']", "", words[-1])
        if not word:
            return
        # Cancel any queued live word and schedule this one
        if self._live_after:
            self.after_cancel(self._live_after)
        self._stop_evt.set()
        winsound.PlaySound(None, winsound.SND_PURGE)
        self._play_btn.configure(state="normal")
        self._live_after = self.after(120, lambda w=word: self._fire_live_word(w))

    def _fire_live_word(self, word):
        self._live_after = None
        self._play(text=word)

    # ──────────────────────────────────────────────────────────── playback ──

    def _play(self, text=None):
        if text is None:
            text = self._txt.get("1.0", "end").strip()
        if not text:
            self._status.configure(text="Type something first!")
            return
        if len(text) > 220:
            self._status.configure(text="Text is too long — keep it shorter.")
            return

        if "Character" in self._tabs.get():
            name      = PRESETS[self._selected][0]
            sam_speed = max(1, self._speed.get())
            sam_pitch = max(1, self._pitch.get())
            params    = (sam_speed, sam_pitch, self._tongue.get(), self._nose.get())
            vol       = self._vol
            if self._singing:
                engine_fn = lambda t: self._say_sam_sing(t, params, vol)
                name = f"{name} ♪"
            else:
                engine_fn = lambda t: self._say_sam(t, params, vol)
        else:
            name  = NAT_VOICES[self._nat_sel][0]
            model = os.path.join(VOICES_DIR, NAT_VOICES[self._nat_sel][2])
            spd   = self._nat_speed
            vol   = self._vol
            if self._singing:
                engine_fn = lambda t: self._say_piper_sing(t, model, spd, vol)
                name = f"{name} ♪"
            else:
                engine_fn = lambda t: self._say_piper(t, model, spd, vol)

        self._play_gen += 1
        gen = self._play_gen
        self._stop_evt.clear()
        self._play_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status.configure(text=f"Speaking as {name}...")
        threading.Thread(target=self._loop_runner,
                         args=(text, engine_fn, gen), daemon=True).start()

    def _loop_runner(self, text, engine_fn, gen):
        while not self._stop_evt.is_set():
            engine_fn(text)
            if not self._looping:
                break
        self.after(0, lambda: self._done(gen))

    # ──────────────────────────────────────────── SAM engine functions ──

    def _say_sam(self, text, params, volume):
        speed, pitch, tongue, nose = params
        winsound.PlaySound(None, winsound.SND_PURGE)
        time.sleep(0.05)
        cmd = [SAM_EXE, "-wav", _TMPWAV,
               "-speed", str(speed), "-pitch", str(pitch),
               "-throat", str(tongue), "-mouth", str(nose),
               *text.split()]
        try:
            subprocess.Popen(cmd,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW).wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"Error: SAM timeout. cmd={cmd}, SAM_EXE={SAM_EXE}")
        self._play_wav(volume)

    def _say_sam_sing(self, text, params, volume):
        """Sing mode: each word on a different note from a pentatonic scale."""
        speed, _, tongue, nose = params
        sing_speed = min(255, speed + 20)
        words = re.sub(r"[^\w\s']", "", text).split()
        if not words:
            return
        tmp_paths = []
        for i, word in enumerate(words):
            if self._stop_evt.is_set():
                break
            pitch = SING_SCALE[i % len(SING_SCALE)]
            tmp   = f"{_TMPWAV}.{i}.wav"
            cmd   = [SAM_EXE, "-wav", tmp,
                     "-speed", str(sing_speed), "-pitch", str(pitch),
                     "-throat", str(tongue), "-mouth", str(nose),
                     word]
            try:
                subprocess.Popen(cmd,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW).wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"Error: SAM sing timeout on word '{word}'")
            if os.path.exists(tmp) and os.path.getsize(tmp) > 44:
                tmp_paths.append(tmp)
        if tmp_paths and not self._stop_evt.is_set():
            _concat_wavs(tmp_paths, _TMPWAV)
            self._play_wav(volume)
        for p in tmp_paths:
            try: os.remove(p)
            except: pass

    # ──────────────────────────────────────────── Piper engine functions ──

    def _say_piper(self, text, model_path, speed, volume):
        winsound.PlaySound(None, winsound.SND_PURGE)
        time.sleep(0.05)
        length_scale = str(round(100.0 / max(1, speed), 3))
        cmd = [PIPER_EXE, "--model", model_path,
               "--output_file", _TMPWAV,
               "--length_scale", length_scale]
        try:
            subprocess.Popen(cmd,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW
                             ).communicate(input=text.encode("utf-8"), timeout=10)
        except subprocess.TimeoutExpired:
            print(f"Error: Piper timeout. cmd={cmd}, PIPER_EXE={PIPER_EXE}")
        self._play_wav(volume)

    def _say_piper_sing(self, text, model_path, speed, volume):
        """Sing mode for natural voices: speech with a musical tremolo effect."""
        winsound.PlaySound(None, winsound.SND_PURGE)
        time.sleep(0.05)
        length_scale = str(round(100.0 / max(1, speed), 3))
        cmd = [PIPER_EXE, "--model", model_path,
               "--output_file", _TMPWAV,
               "--length_scale", length_scale]
        try:
            subprocess.Popen(cmd,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW
                             ).communicate(input=text.encode("utf-8"), timeout=10)
        except subprocess.TimeoutExpired:
            print(f"Error: Piper sing timeout. cmd={cmd}")
        self._play_wav(volume, sing=True)

    # ─────────────────────────────────────────────────── shared playback ──

    def _play_wav(self, volume, sing=False):
        if not os.path.exists(_TMPWAV) or os.path.getsize(_TMPWAV) == 0:
            return
        _process_wav(_TMPWAV, volume, sing=sing)
        with wave.open(_TMPWAV, "rb") as wf:
            duration = wf.getnframes() / wf.getframerate()
        winsound.PlaySound(_TMPWAV, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elapsed = 0.0
        while elapsed < duration and not self._stop_evt.is_set():
            time.sleep(0.05)
            elapsed += 0.05
        if self._stop_evt.is_set():
            winsound.PlaySound(None, winsound.SND_PURGE)

    def _stop(self):
        self._stop_evt.set()
        winsound.PlaySound(None, winsound.SND_PURGE)

    def _done(self, gen):
        if gen != self._play_gen:
            return                                  # superseded by a newer _play call
        self._play_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        if not self._live_mode:
            self._status.configure(text="")
        else:
            self._status.configure(text="Live mode: press Space after each word")


if __name__ == "__main__":
    app = VoiceMachine()
    app.mainloop()


