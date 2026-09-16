"""
login_window.py — clinic_app_v5 (NEW)

A self-contained, animated login screen for the clinic app, built purely
with customtkinter + tkinter (no extra GUI/animation libraries needed):

  - Soft vertical gradient backdrop (drawn on a plain tkinter Canvas)
  - A "floating card" with a layered drop-shadow (offset frames behind
    the card — the classic flat-UI shadow technique)
  - Slide-up + ease-out entrance animation when the window opens
  - A shake animation on failed login / failed reset
  - Live focus highlighting on inputs, hover-animated buttons
  - A show/hide toggle on password fields
  - Three views inside the same card: Sign in → Forgot password
    (security question) → Create admin account (shown automatically the
    very first time the app is run, before any user exists)

Usage (see main.py):

    from ui.login_window import run_login
    user = run_login()
    if not user:
        sys.exit(0)
"""

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from core import auth_manager
from config import CONFIG

try:
    from PIL import Image
except ImportError:
    Image = None


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Palette (matches the #2C4A7C accent already used in the PDF header) ──
ACCENT        = "#2C4A7C"
ACCENT_LIGHT  = "#3E63A8"
GRADIENT_TOP  = "#0F2547"
GRADIENT_BOT  = "#2C6E7C"
CARD_BG       = "#FFFFFF"
PANE_BG       = "#F5F7FA"
BORDER        = "#D8DEE9"
TEXT_MUTED    = "#6B7280"
ERROR_RED     = "#D64545"
SUCCESS_GREEN = "#2E9E5B"

SECURITY_QUESTIONS = [
    "What was your childhood nickname?",
    "What is the name of your first pet?",
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What was the name of your first school?",
]


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class LoginWindow(ctk.CTk):

    CARD_W, CARD_H = 860, 520

    def __init__(self):
        super().__init__()
        self.result_user = None

        self.title(f"{CONFIG.get('clinic_name', 'Clinic')} — Sign in")
        self.geometry("1040x680")
        self.minsize(900, 600)
        self.configure(fg_color=GRADIENT_TOP)
        self._center_on_screen()

        # ---- gradient background ----
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_gradient)

        # ---- shadow layers + card ----
        self.shadow_far = ctk.CTkFrame(self, corner_radius=26, fg_color="#08152C",
                                        width=self.CARD_W, height=self.CARD_H)
        self.shadow_near = ctk.CTkFrame(self, corner_radius=24, fg_color="#122542",
                                         width=self.CARD_W, height=self.CARD_H)
        self.card = ctk.CTkFrame(self, corner_radius=22, fg_color=CARD_BG,
                                  width=self.CARD_W, height=self.CARD_H)

        # ---- two panes inside the card ----
        self.left_pane = ctk.CTkFrame(self.card, corner_radius=0, fg_color=ACCENT,
                                       width=320, height=self.CARD_H - 4)
        self.right_pane = ctk.CTkFrame(self.card, corner_radius=0, fg_color=CARD_BG,
                                        width=self.CARD_W - 320 - 4, height=self.CARD_H - 4)
        self.left_pane.place(x=2, y=2)
        self.right_pane.place(x=322, y=2)

        self._build_left_pane()

        self.form_area = ctk.CTkFrame(self.right_pane, fg_color="transparent")
        self.form_area.place(relx=0.5, rely=0.5, anchor="center",
                              relwidth=0.82, relheight=0.9)

        self._place_card_group(0.62)  # start off-screen (below), animate up
        self._show_initial_view()
        self.after(30, self._animate_entrance)

    # ─────────────────────────────────────────────
    #  Window chrome / background
    # ─────────────────────────────────────────────

    def _center_on_screen(self):
        self.update_idletasks()
        w, h = 1040, 680
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _draw_gradient(self, event=None):
        self.bg_canvas.delete("grad")
        width = self.bg_canvas.winfo_width()
        height = self.bg_canvas.winfo_height()
        if width < 2 or height < 2:
            return
        r1, g1, b1 = _hex_to_rgb(GRADIENT_TOP)
        r2, g2, b2 = _hex_to_rgb(GRADIENT_BOT)
        steps = 90
        for i in range(steps):
            t = i / steps
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            color = f"#{r:02x}{g:02x}{b:02x}"
            y0 = int(height * i / steps)
            y1 = int(height * (i + 1) / steps) + 1
            self.bg_canvas.create_rectangle(0, y0, width, y1, fill=color,
                                             outline="", tags="grad")
        self.bg_canvas.tag_lower("grad")

    # ─────────────────────────────────────────────
    #  Card positioning + animation
    # ─────────────────────────────────────────────

    def _place_card_group(self, rely, x_offset=0):
        self.shadow_far.place(relx=0.5, rely=rely, anchor="center",
                               x=x_offset + 12, y=16)
        self.shadow_near.place(relx=0.5, rely=rely, anchor="center",
                                x=x_offset + 6, y=8)
        self.card.place(relx=0.5, rely=rely, anchor="center", x=x_offset)

    def _animate_entrance(self):
        steps = 20
        start, end = 0.62, 0.5

        def step(i=0):
            t = i / steps
            eased = 1 - (1 - t) ** 3  # ease-out cubic
            rely = start + (end - start) * eased
            self._place_card_group(rely)
            if i < steps:
                self.after(12, lambda: step(i + 1))
        step()

    def _shake_card(self):
        offsets = [-16, 14, -12, 10, -6, 4, 0]

        def step(i=0):
            if i >= len(offsets):
                self._place_card_group(0.5)
                return
            self._place_card_group(0.5, x_offset=offsets[i])
            self.after(35, lambda: step(i + 1))
        step()

    # ─────────────────────────────────────────────
    #  Left branding pane
    # ─────────────────────────────────────────────

    def _build_left_pane(self):
        deco = tk.Canvas(self.left_pane, width=320, height=self.CARD_H - 4,
                          highlightthickness=0, bd=0, bg=ACCENT)
        deco.place(x=0, y=0)
        deco.create_oval(-60, -60, 140, 140, fill=ACCENT_LIGHT, outline="")
        deco.create_oval(210, self.CARD_H - 160, 420, self.CARD_H + 60,
                          fill=ACCENT_LIGHT, outline="")

        content = ctk.CTkFrame(self.left_pane, fg_color="transparent",
                                width=280, height=self.CARD_H - 60)
        content.place(relx=0.5, rely=0.5, anchor="center")

        logo_img = self._load_logo(size=(76, 76))
        if logo_img is not None:
            ctk.CTkLabel(content, image=logo_img, text="").pack(pady=(10, 18))
        else:
            initials = "".join(w[0] for w in
                                CONFIG.get("clinic_name", "Clinic")[:2].split())[:2].upper() or "C"
            badge = ctk.CTkLabel(
                content, text=initials, width=76, height=76, corner_radius=38,
                fg_color=ACCENT_LIGHT, text_color="white",
                font=ctk.CTkFont(size=26, weight="bold")
            )
            badge.pack(pady=(10, 18))

        ctk.CTkLabel(content, text=CONFIG.get("clinic_name", "Clinic"),
                      text_color="white", font=ctk.CTkFont(size=22, weight="bold"),
                      wraplength=260, justify="center").pack()
        ctk.CTkLabel(content, text=CONFIG.get("doctor_name", ""),
                      text_color="#C9D6EA", font=ctk.CTkFont(size=13),
                      wraplength=260, justify="center").pack(pady=(2, 0))
        ctk.CTkLabel(content, text="Patient Management System",
                      text_color="#9FB3D6", font=ctk.CTkFont(size=12),
                      wraplength=240, justify="center").pack(pady=(22, 0))

        addr = CONFIG.get("clinic_address", "")
        phone = CONFIG.get("clinic_phone", "")
        footer = " • ".join(p for p in (addr, phone) if p)
        if footer:
            ctk.CTkLabel(content, text=footer, text_color="#8DA2C7",
                         font=ctk.CTkFont(size=10), wraplength=250,
                         justify="center").pack(side="bottom", pady=(20, 0))

    def _load_logo(self, size=(76, 76)):
        if Image is None:
            return None
        path = Path(__file__).parent.parent / CONFIG.get("clinic_logo_path", "assets/logo.png")
        if not path.exists():
            return None
        try:
            img = Image.open(path)
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            return None

    # ─────────────────────────────────────────────
    #  View management
    # ─────────────────────────────────────────────

    def _clear_form(self):
        for child in self.form_area.winfo_children():
            child.destroy()
        self.unbind("<Return>")

    def _show_initial_view(self):
        if auth_manager.has_any_users():
            self._show_login_view()
        else:
            self._show_register_view()

    # ---------- reusable widgets ----------

    def _heading(self, parent, title, subtitle):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=24, weight="bold"),
                      text_color="#1A2333", anchor="w").pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(parent, text=subtitle, font=ctk.CTkFont(size=13),
                      text_color=TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 18))

    def _make_entry(self, parent, placeholder, show=""):
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, show=show,
                              height=44, corner_radius=10, border_width=1.5,
                              border_color=BORDER, fg_color=PANE_BG,
                              font=ctk.CTkFont(size=13))
        entry.bind("<FocusIn>", lambda e: entry.configure(border_color=ACCENT))
        entry.bind("<FocusOut>", lambda e: entry.configure(border_color=BORDER))
        return entry

    def _make_password_row(self, parent, placeholder):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        entry = self._make_entry(row, placeholder, show="*")
        entry.pack(side="left", fill="x", expand=True)

        state = {"visible": False}

        def toggle():
            state["visible"] = not state["visible"]
            entry.configure(show="" if state["visible"] else "*")
            eye_btn.configure(text="🙈" if state["visible"] else "👁")

        eye_btn = ctk.CTkButton(row, text="👁", width=40, height=44, corner_radius=10,
                                 fg_color=PANE_BG, hover_color=BORDER,
                                 text_color=TEXT_MUTED, command=toggle)
        eye_btn.pack(side="left", padx=(8, 0))
        return row, entry

    def _make_primary_button(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, command=command, height=46,
                              corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_LIGHT,
                              font=ctk.CTkFont(size=14, weight="bold"))

    def _make_link_button(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, command=command, fg_color="transparent",
                              hover_color=PANE_BG, text_color=ACCENT, height=28,
                              font=ctk.CTkFont(size=12, underline=True))

    def _make_message_label(self, parent):
        label = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=12),
                              text_color=ERROR_RED, wraplength=320, justify="left")
        return label

    def _flash_message(self, label, text, ok=False):
        label.configure(text=text, text_color=SUCCESS_GREEN if ok else ERROR_RED)
        if not ok:
            self._shake_card()

    # ─────────────────────────────────────────────
    #  Sign-in view
    # ─────────────────────────────────────────────

    def _show_login_view(self):
        self._clear_form()
        f = self.form_area
        self._heading(f, "Welcome back", "Sign in to continue")

        ctk.CTkLabel(f, text="Username", font=ctk.CTkFont(size=12),
                      text_color=TEXT_MUTED, anchor="w").pack(fill="x")
        username_entry = self._make_entry(f, "Enter your username")
        username_entry.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(f, text="Password", font=ctk.CTkFont(size=12),
                      text_color=TEXT_MUTED, anchor="w").pack(fill="x")
        pw_row, password_entry = self._make_password_row(f, "Enter your password")
        pw_row.pack(fill="x", pady=(4, 6))

        msg = self._make_message_label(f)
        msg.pack(fill="x", pady=(2, 10))

        def submit(event=None):
            username = username_entry.get().strip()
            password = password_entry.get()
            if not username or not password:
                self._flash_message(msg, "Please enter both username and password.")
                return
            result = auth_manager.verify_login(username, password)
            if result["ok"]:
                self.result_user = result["user"]
                msg.configure(text_color=SUCCESS_GREEN)
                self._flash_message(msg, f"Welcome, {result['user'].get('full_name') or username}!", ok=True)
                self.after(450, self.destroy)
            else:
                password_entry.delete(0, "end")
                self._flash_message(msg, result["error"])
                password_entry.focus_set()

        self._make_primary_button(f, "Sign In", submit).pack(fill="x", pady=(4, 10))

        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.pack(fill="x")
        self._make_link_button(bottom, "Forgot password?",
                                lambda: self._show_forgot_step1()).pack(side="right")

        self.bind("<Return>", submit)
        username_entry.focus_set()

    # ─────────────────────────────────────────────
    #  First-run: create admin account
    # ─────────────────────────────────────────────

    def _show_register_view(self):
        self._clear_form()
        f = self.form_area
        self._heading(f, "Create your account",
                       "First time setup — this becomes the clinic admin login")

        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        name_entry = self._make_entry(scroll, "Full name")
        name_entry.pack(fill="x", pady=(0, 10))
        username_entry = self._make_entry(scroll, "Choose a username")
        username_entry.pack(fill="x", pady=(0, 10))
        pw_row, password_entry = self._make_password_row(scroll, "Choose a password (min 6 chars)")
        pw_row.pack(fill="x", pady=(0, 10))
        pw2_row, confirm_entry = self._make_password_row(scroll, "Confirm password")
        pw2_row.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(scroll, text="Security question (used to reset your password)",
                      font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
                      anchor="w", wraplength=320).pack(fill="x")
        question_box = ctk.CTkComboBox(scroll, values=SECURITY_QUESTIONS,
                                        height=44, corner_radius=10,
                                        border_color=BORDER, fg_color=PANE_BG,
                                        button_color=ACCENT, button_hover_color=ACCENT_LIGHT)
        question_box.set(SECURITY_QUESTIONS[0])
        question_box.pack(fill="x", pady=(4, 10))
        answer_entry = self._make_entry(scroll, "Your answer")
        answer_entry.pack(fill="x", pady=(0, 8))

        msg = self._make_message_label(scroll)
        msg.pack(fill="x", pady=(2, 10))

        def submit(event=None):
            if password_entry.get() != confirm_entry.get():
                self._flash_message(msg, "Passwords don't match.")
                return
            try:
                auth_manager.create_user(
                    username=username_entry.get(),
                    full_name=name_entry.get(),
                    password=password_entry.get(),
                    security_question=question_box.get(),
                    security_answer=answer_entry.get(),
                    role="admin",
                )
            except ValueError as e:
                self._flash_message(msg, str(e))
                return

            result = auth_manager.verify_login(username_entry.get().strip(), password_entry.get())
            if result["ok"]:
                self.result_user = result["user"]
                self._flash_message(msg, "Account created — signing you in...", ok=True)
                self.after(500, self.destroy)

        self._make_primary_button(scroll, "Create Account", submit).pack(fill="x", pady=(6, 4))
        self.bind("<Return>", submit)
        name_entry.focus_set()

    # ─────────────────────────────────────────────
    #  Forgot password — step 1: which account?
    # ─────────────────────────────────────────────

    def _show_forgot_step1(self):
        self._clear_form()
        f = self.form_area
        self._heading(f, "Reset your password", "Enter your username to continue")

        username_entry = self._make_entry(f, "Username")
        username_entry.pack(fill="x", pady=(0, 10))

        msg = self._make_message_label(f)
        msg.pack(fill="x", pady=(2, 10))

        def submit(event=None):
            username = username_entry.get().strip()
            question = auth_manager.get_security_question(username)
            if not question:
                self._flash_message(msg, "No account with that username.")
                return
            self._show_forgot_step2(username, question)

        self._make_primary_button(f, "Continue", submit).pack(fill="x", pady=(6, 10))
        self._make_link_button(f, "← Back to Sign In",
                                lambda: self._show_login_view()).pack(anchor="w")

        self.bind("<Return>", submit)
        username_entry.focus_set()

    # ─────────────────────────────────────────────
    #  Forgot password — step 2: answer + new password
    # ─────────────────────────────────────────────

    def _show_forgot_step2(self, username, question):
        self._clear_form()
        f = self.form_area
        self._heading(f, "Security check", "Answer your security question to reset it")

        ctk.CTkLabel(f, text=question, font=ctk.CTkFont(size=13, weight="bold"),
                      text_color="#1A2333", anchor="w", wraplength=320,
                      justify="left").pack(fill="x", pady=(0, 8))
        answer_entry = self._make_entry(f, "Your answer")
        answer_entry.pack(fill="x", pady=(0, 10))

        pw_row, new_pw_entry = self._make_password_row(f, "New password (min 6 chars)")
        pw_row.pack(fill="x", pady=(0, 10))

        msg = self._make_message_label(f)
        msg.pack(fill="x", pady=(2, 10))

        def submit(event=None):
            result = auth_manager.reset_password(username, answer_entry.get(), new_pw_entry.get())
            if result["ok"]:
                self._flash_message(msg, "Password reset! Redirecting to sign in...", ok=True)
                self.after(900, self._show_login_view)
            else:
                self._flash_message(msg, result["error"])

        self._make_primary_button(f, "Reset Password", submit).pack(fill="x", pady=(6, 10))
        self._make_link_button(f, "← Back to Sign In",
                                lambda: self._show_login_view()).pack(anchor="w")

        self.bind("<Return>", submit)
        answer_entry.focus_set()

    # ─────────────────────────────────────────────
    #  Entry point
    # ─────────────────────────────────────────────

    def run(self):
        self.mainloop()
        return self.result_user


def run_login():
    """
    Opens the login window (blocking) and returns the logged-in user dict
    on success, or None if the window was closed without logging in.

    If CONFIG['login_enabled'] is False, skips straight through — handy
    while you're still wiring things up.
    """
    if not CONFIG.get("login_enabled", True):
        return {"username": "guest", "full_name": "Guest", "role": "guest"}
    window = LoginWindow()
    return window.run()
