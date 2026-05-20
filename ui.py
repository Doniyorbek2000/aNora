import os, json, time, math, random, threading
import tkinter as tk
from collections import deque
from PIL import Image, ImageTk, ImageDraw
import sys
from pathlib import Path
from memory.config_manager import is_configured, save_api_keys


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

SYSTEM_NAME = "NORA"
MODEL_BADGE = "NORA"

# Enhanced color palette with gradients and modern colors
C_BG     = "#0a0a0a"  # Darker background
C_PRI    = "#00e5ff"  # Bright cyan
C_MID    = "#0088aa"  # Medium blue
C_DIM    = "#004455"  # Dark blue
C_DIMMER = "#001a22"  # Very dark blue
C_ACC    = "#ff4081"  # Pink accent
C_ACC2   = "#ffeb3b"  # Yellow accent
C_TEXT   = "#e1f5fe"  # Light blue text
C_PANEL  = "#0f1419"  # Dark panel
C_GREEN  = "#00e676"  # Bright green
C_RED    = "#ff5252"  # Bright red
C_PURPLE = "#9c27b0"  # Purple accent
C_ORANGE = "#ff9800"  # Orange accent


class NoraUI:
    def __init__(self, face_path, size=None):
        self.root = tk.Tk()
        self.root.title("NORA — Personal AI")
        self.root.resizable(False, False)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        W  = min(sw, 984)
        H  = min(sh, 816)
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.root.configure(bg=C_BG)

        self.W = W
        self.H = H

        self.FACE_SZ = min(int(H * 0.54), 400)
        self.FCX     = W // 2
        self.FCY     = int(H * 0.13) + self.FACE_SZ // 2

        self.speaking     = False
        self.scale        = 1.0
        self.target_scale = 1.0
        self.halo_a       = 60.0
        self.target_halo  = 60.0
        self.last_t       = time.time()
        self.tick         = 0
        self.scan_angle   = 0.0
        self.scan2_angle  = 180.0
        self.rings_spin   = [0.0, 120.0, 240.0]
        self.pulse_r      = [0.0, self.FACE_SZ * 0.26, self.FACE_SZ * 0.52]
        self.status_text  = "INITIALISING"
        self.status_blink = True

        self.typing_queue = deque()
        self.is_typing    = False

        self._face_pil         = None
        self._has_face         = False
        self._face_scale_cache = None
        self._load_face(face_path)

        self.bg = tk.Canvas(self.root, width=W, height=H,
                            bg=C_BG, highlightthickness=0)
        self.bg.place(x=0, y=0)

        LW = int(W * 0.72)
        LH = 138
        self.log_frame = tk.Frame(self.root, bg=C_PANEL,
                                  highlightbackground=C_MID,
                                  highlightthickness=1)
        self.log_frame.place(x=(W - LW) // 2, y=H - LH - 36, width=LW, height=LH)
        self.log_text = tk.Text(self.log_frame, fg=C_TEXT, bg=C_PANEL,
                                insertbackground=C_TEXT, borderwidth=0,
                                wrap="word", font=("Courier", 10), padx=10, pady=6)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.tag_config("you", foreground="#e8e8e8")
        self.log_text.tag_config("ai",  foreground=C_PRI)
        self.log_text.tag_config("sys", foreground=C_ACC2)

        self._api_key_ready = self._api_keys_exist()
        if not self._api_key_ready:
            self._show_setup_ui()

        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    def _load_face(self, path):
        FW = self.FACE_SZ
        try:
            img  = Image.open(path).convert("RGBA").resize((FW, FW), Image.LANCZOS)
            mask = Image.new("L", (FW, FW), 0)
            ImageDraw.Draw(mask).ellipse((2, 2, FW - 2, FW - 2), fill=255)
            img.putalpha(mask)
            self._face_pil = img
            self._has_face = True
        except Exception:
            self._has_face = False

    @staticmethod
    def _ac(r, g, b, a):
        f = a / 255.0
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"

    def _animate(self):
        self.tick += 1
        t   = self.tick
        now = time.time()

        if now - self.last_t > (0.12 if self.speaking else 0.45):
            if self.speaking:
                self.target_scale = random.uniform(1.08, 1.15)
                self.target_halo  = random.uniform(160, 220)
            else:
                self.target_scale = random.uniform(1.002, 1.008)
                self.target_halo  = random.uniform(55, 75)
            self.last_t = now

        sp = 0.42 if self.speaking else 0.18
        self.scale  += (self.target_scale - self.scale) * sp
        self.halo_a += (self.target_halo  - self.halo_a) * sp

        # Enhanced ring animations with varying speeds
        for i, spd in enumerate([1.5, -1.1, 2.2, 0.8] if self.speaking else [0.6, -0.4, 0.95, 0.3]):
            if i < len(self.rings_spin):
                self.rings_spin[i] = (self.rings_spin[i] + spd) % 360
            else:
                self.rings_spin.append(0.0)

        self.scan_angle  = (self.scan_angle  + (3.2 if self.speaking else 1.4)) % 360
        self.scan2_angle = (self.scan2_angle + (-2.1 if self.speaking else -0.75)) % 360

        # More dynamic pulse effects
        pspd  = 4.5 if self.speaking else 2.1
        limit = self.FACE_SZ * 0.78
        new_p = [r + pspd for r in self.pulse_r if r + pspd < limit]
        if len(new_p) < 4 and random.random() < (0.08 if self.speaking else 0.025):
            new_p.append(0.0)
        self.pulse_r = new_p[:4]  # Limit to 4 pulses

        if t % 35 == 0:
            self.status_blink = not self.status_blink

        self._draw()
        self.root.after(14, self._animate)  # Slightly faster animation

    def _draw(self):
        c    = self.bg
        W, H = self.W, self.H
        t    = self.tick
        FCX  = self.FCX
        FCY  = self.FCY
        FW   = self.FACE_SZ
        c.delete("all")

        # Enhanced background grid with gradient
        for x in range(0, W, 38):
            for y in range(0, H, 38):
                intensity = int(25 + 15 * math.sin(x * 0.01 + y * 0.01 + t * 0.02))
                color = f"#{intensity:02x}{intensity:02x}{intensity+10:02x}"
                c.create_rectangle(x, y, x+1, y+1, fill=color, outline="")

        # Multi-layered halo effects with different colors
        halo_colors = [C_PRI, C_ACC, C_PURPLE, C_ORANGE]
        for i, color in enumerate(halo_colors):
            for r in range(int(FW * (0.6 - i*0.08)), int(FW * (0.35 - i*0.08)), -18):
                frac = 1.0 - (r - FW * (0.35 - i*0.08)) / (FW * 0.25)
                ga   = max(0, min(255, int(self.halo_a * 0.08 * frac * (1 + i*0.3))))
                if color == C_PRI:
                    c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                                  outline=self._ac(0, 229, 255, ga), width=2)
                elif color == C_ACC:
                    c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                                  outline=self._ac(255, 64, 129, ga), width=2)
                elif color == C_PURPLE:
                    c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                                  outline=self._ac(156, 39, 176, ga), width=2)
                else:
                    c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                                  outline=self._ac(255, 152, 0, ga), width=2)

        # Enhanced pulse rings with color variation
        pulse_colors = [C_PRI, C_ACC, C_GREEN, C_PURPLE]
        for i, pr in enumerate(self.pulse_r):
            color = pulse_colors[i % len(pulse_colors)]
            pa = max(0, int(240 * (1.0 - pr / (FW * 0.78))))
            r  = int(pr)
            if color == C_PRI:
                c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                              outline=self._ac(0, 229, 255, pa), width=3)
            elif color == C_ACC:
                c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                              outline=self._ac(255, 64, 129, pa), width=3)
            elif color == C_GREEN:
                c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                              outline=self._ac(0, 230, 118, pa), width=3)
            else:
                c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r,
                              outline=self._ac(156, 39, 176, pa), width=3)

        # Enhanced rotating rings with more dynamic effects
        for idx, (r_frac, w_ring, arc_l, gap) in enumerate([
                (0.52, 4, 120, 80), (0.44, 3, 85, 60), (0.36, 2, 65, 45), (0.28, 1, 45, 30)]):
            ring_r = int(FW * r_frac)
            base_a = self.rings_spin[idx] if idx < len(self.rings_spin) else 0
            a_val  = max(0, min(255, int(self.halo_a * (1.2 - idx * 0.25))))

            # Color cycle for rings
            ring_color = [C_PRI, C_ACC, C_PURPLE, C_ORANGE][idx % 4]
            if ring_color == C_PRI:
                col = self._ac(0, 229, 255, a_val)
            elif ring_color == C_ACC:
                col = self._ac(255, 64, 129, a_val)
            elif ring_color == C_PURPLE:
                col = self._ac(156, 39, 176, a_val)
            else:
                col = self._ac(255, 152, 0, a_val)

            for s in range(360 // (arc_l + gap)):
                start = (base_a + s * (arc_l + gap)) % 360
                c.create_arc(FCX-ring_r, FCY-ring_r, FCX+ring_r, FCY+ring_r,
                             start=start, extent=arc_l,
                             outline=col, width=w_ring, style="arc")

        # Dual scanning arcs with enhanced effects
        sr      = int(FW * 0.53)
        scan_a  = min(255, int(self.halo_a * 1.6))
        arc_ext = 80 if self.speaking else 48

        # Primary scan (cyan)
        c.create_arc(FCX-sr, FCY-sr, FCX+sr, FCY+sr,
                     start=self.scan_angle, extent=arc_ext,
                     outline=self._ac(0, 229, 255, scan_a), width=4, style="arc")

        # Secondary scan (pink)
        c.create_arc(FCX-sr, FCY-sr, FCX+sr, FCY+sr,
                     start=self.scan2_angle, extent=arc_ext,
                     outline=self._ac(255, 64, 129, scan_a // 1.5), width=3, style="arc")

        # Enhanced targeting crosshairs
        t_out = int(FW * 0.52)
        t_in  = int(FW * 0.49)
        a_mk  = self._ac(0, 229, 255, 180)
        for deg in range(0, 360, 8):  # More ticks
            rad = math.radians(deg)
            inn = t_in if deg % 45 == 0 else t_in + 6
            c.create_line(FCX + t_out * math.cos(rad), FCY - t_out * math.sin(rad),
                          FCX + inn  * math.cos(rad), FCY - inn  * math.sin(rad),
                          fill=a_mk, width=2)

        # Larger crosshair lines
        ch_r = int(FW * 0.54)
        gap  = int(FW * 0.18)
        ch_a = self._ac(0, 229, 255, int(self.halo_a * 0.65))
        for x1, y1, x2, y2 in [
                (FCX - ch_r, FCY, FCX - gap, FCY), (FCX + gap, FCY, FCX + ch_r, FCY),
                (FCX, FCY - ch_r, FCX, FCY - gap), (FCX, FCY + gap, FCX, FCY + ch_r)]:
            c.create_line(x1, y1, x2, y2, fill=ch_a, width=3)

        # Corner brackets with enhanced styling
        blen = 28
        bc   = self._ac(0, 229, 255, 220)
        hl = FCX - FW // 2; hr = FCX + FW // 2
        ht = FCY - FW // 2; hb = FCY + FW // 2
        for bx, by, sdx, sdy in [(hl, ht, 1, 1), (hr, ht, -1, 1),
                                   (hl, hb, 1, -1), (hr, hb, -1, -1)]:
            c.create_line(bx, by, bx + sdx * blen, by,            fill=bc, width=3)
            c.create_line(bx, by, bx,               by + sdy * blen, fill=bc, width=3)

        if self._has_face:
            fw = int(FW * self.scale)
            if (self._face_scale_cache is None or
                    abs(self._face_scale_cache[0] - self.scale) > 0.004):
                scaled = self._face_pil.resize((fw, fw), Image.BILINEAR)
                tk_img = ImageTk.PhotoImage(scaled)
                self._face_scale_cache = (self.scale, tk_img)
            c.create_image(FCX, FCY, image=self._face_scale_cache[1])
        else:
            orb_r = int(FW * 0.27 * self.scale)
            for i in range(7, 0, -1):
                r2   = int(orb_r * i / 7)
                frac = i / 7
                ga   = max(0, min(255, int(self.halo_a * 1.1 * frac)))
                c.create_oval(FCX-r2, FCY-r2, FCX+r2, FCY+r2,
                              fill=self._ac(0, int(65*frac), int(120*frac), ga),
                              outline="")
            c.create_text(FCX, FCY, text=SYSTEM_NAME,
                          fill=self._ac(0, 212, 255, min(255, int(self.halo_a * 2))),
                          font=("Courier", 14, "bold"))

        HDR = 62
        c.create_rectangle(0, 0, W, HDR, fill="#00080d", outline="")
        c.create_line(0, HDR, W, HDR, fill=C_MID, width=1)
        c.create_text(W // 2, 22, text=SYSTEM_NAME,
                      fill=C_PRI, font=("Courier", 18, "bold"))
        c.create_text(W // 2, 44, text="NORA — Intelligent Personal Assistant",
                      fill=C_MID, font=("Courier", 9))
        c.create_text(16, 31,    text=MODEL_BADGE,
                      fill=C_DIM, font=("Courier", 9), anchor="w")
        c.create_text(W - 16, 31, text=time.strftime("%H:%M:%S"),
                      fill=C_PRI, font=("Courier", 14, "bold"), anchor="e")


        sy = FCY + FW // 2 + 45
        if self.speaking:
            stat, sc = "● SPEAKING", C_ACC
        else:
            sym = "●" if self.status_blink else "○"
            stat, sc = f"{sym} {self.status_text}", C_PRI

        c.create_text(W // 2, sy, text=stat,
                      fill=sc, font=("Courier", 11, "bold"))

        wy = sy + 22
        N  = 32
        BH = 18
        bw = 8
        total_w = N * bw
        wx0 = (W - total_w) // 2
        for i in range(N):
            hb  = random.randint(3, BH) if self.speaking else int(3 + 2 * math.sin(t * 0.08 + i * 0.55))
            col = (C_PRI if hb > BH * 0.6 else C_MID) if self.speaking else C_DIM
            bx  = wx0 + i * bw
            c.create_rectangle(bx, wy + BH - hb, bx + bw - 1, wy + BH,
                                fill=col, outline="")

        c.create_rectangle(0, H - 28, W, H, fill="#00080d", outline="")
        c.create_line(0, H - 28, W, H - 28, fill=C_DIM, width=1)
        c.create_text(W // 2, H - 14, fill=C_DIM, font=("Courier", 8),
                      text="FatihMakes Industries  ·  CLASSIFIED  ·  NORA")

    def write_log(self, text: str):
        self.typing_queue.append(text)
        tl = text.lower()
        self.status_text = ("PROCESSING" if tl.startswith("you:")
                            else "RESPONDING" if tl.startswith("ai:")
                            else self.status_text)
        if not self.is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            if not self.speaking:
                self.status_text = "ONLINE"
            return
        self.is_typing = True
        text = self.typing_queue.popleft()
        tl   = text.lower()
        tag  = "you" if tl.startswith("you:") else "ai" if tl.startswith("ai:") else "sys"
        self.log_text.configure(state="normal")
        self._type_char(text, 0, tag)

    def _type_char(self, text, i, tag):
        if i < len(text):
            self.log_text.insert(tk.END, text[i], tag)
            self.log_text.see(tk.END)
            self.root.after(8, self._type_char, text, i + 1, tag)
        else:
            self.log_text.insert(tk.END, "\n")
            self.log_text.configure(state="disabled")
            self.root.after(25, self._start_typing)

    def start_speaking(self):
        self.speaking    = True
        self.status_text = "SPEAKING"

    def stop_speaking(self):
        self.speaking    = False
        self.status_text = "ONLINE"

    def _api_keys_exist(self):
        return is_configured()

    def wait_for_api_key(self):
        """Block until API key is saved (called from main thread before starting NORA)."""
        while not self._api_key_ready:
            time.sleep(0.1)

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(
            self.root, bg="#00080d",
            highlightbackground=C_PRI, highlightthickness=1
        )
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(self.setup_frame, text="◈  INITIALISATION REQUIRED",
                 fg=C_PRI, bg="#00080d", font=("Courier", 13, "bold")).pack(pady=(18, 4))
        tk.Label(self.setup_frame,
                 text="Enter your Gemini API key to boot NORA.",
                 fg=C_MID, bg="#00080d", font=("Courier", 9)).pack(pady=(0, 10))

        tk.Label(self.setup_frame, text="GEMINI API KEY",
                 fg=C_DIM, bg="#00080d", font=("Courier", 9)).pack(pady=(8, 2))
        self.gemini_entry = tk.Entry(
            self.setup_frame, width=52, fg=C_TEXT, bg="#000d12",
            insertbackground=C_TEXT, borderwidth=0, font=("Courier", 10), show="*"
        )
        self.gemini_entry.pack(pady=(0, 4))

        tk.Button(
            self.setup_frame, text="▸  INITIALISE SYSTEMS",
            command=self._save_api_keys, bg=C_BG, fg=C_PRI,
            activebackground="#003344", font=("Courier", 10),
            borderwidth=0, pady=8
        ).pack(pady=14)

    def _save_api_keys(self):
        gemini = self.gemini_entry.get().strip()
        if not gemini:
            return
        save_api_keys(gemini)
        self.setup_frame.destroy()
        self._api_key_ready = True
        self.status_text = "ONLINE"
        self.write_log("SYS: Systems initialised. NORA online.")