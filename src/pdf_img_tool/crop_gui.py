import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Literal

from PIL import Image, ImageTk

from pdf_img_tool.crop_core import (
    auto_trim_bbox,
    compute_display_scale,
    compute_display_size,
    rotate_crop_box,
    save_cropped_image,
)
from pdf_img_tool.models import CropBox, CropResult

MAX_CANVAS_WIDTH = 1200
MAX_CANVAS_HEIGHT = 800
MIN_ZOOM = 0.2
MAX_ZOOM = 8.0
ZOOM_STEP = 1.1


class CropWindow:
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        *,
        window_title: str,
        progress_text: str,
        initial_crop_box: CropBox | None,
        allow_back: bool,
        auto_trim_threshold: int,
        auto_trim_padding: int,
        output_format: str | None,
        jpeg_quality: int,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.window_title_base = window_title
        self.progress_text = progress_text
        self.allow_back = allow_back
        self.auto_trim_threshold = auto_trim_threshold
        self.auto_trim_padding = auto_trim_padding
        self.output_format = output_format
        self.jpeg_quality = jpeg_quality
        self.result = CropResult(action="cancel")

        self.root = tk.Tk()
        self.root.title(window_title)
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self._configure_style()

        self.original_image = Image.open(input_path)
        self.view_image = self.original_image
        self.rotation_deg = 0
        self.base_scale = 1.0
        self.zoom = 1.0

        self.canvas_width = 1
        self.canvas_height = 1
        self._update_view_geometry()

        self.pan_x = 0.0
        self.pan_y = 0.0
        self.drag_start_canvas_x = 0
        self.drag_start_canvas_y = 0

        self.is_panning = False
        self.space_held = False

        self.selection_box: CropBox | None = None
        self.drag_start_image_x = 0
        self.drag_start_image_y = 0

        self.crosshair_x_id: int | None = None
        self.crosshair_y_id: int | None = None
        self.selection_rect_id: int | None = None
        self.overlay_ids: list[int] = []
        self.image_item_id: int | None = None

        self.display_image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.scaled_width = 1
        self.scaled_height = 1

        self.info_zoom = tk.StringVar(value="100%")
        self.info_image_size = tk.StringVar(
            value=f"{self.view_image.width} x {self.view_image.height}"
        )
        self.info_crop = tk.StringVar(value="x=0, y=0, w=0, h=0")
        self.info_output = tk.StringVar(value=str(self.output_path))
        self.info_progress = tk.StringVar(value=self.progress_text)

        self._build_layout()
        self._update_window_title()

        self._apply_initial_selection(initial_crop_box)
        self._rerender_image()
        self._clamp_pan()
        self._redraw_scene()

    def _update_window_title(self) -> None:
        self.root.title(f"{self.window_title_base} [{self.rotation_deg}\N{DEGREE SIGN}]")

    def _update_view_geometry(self) -> None:
        self.base_scale = compute_display_scale(
            self.view_image.width,
            self.view_image.height,
            max_width=MAX_CANVAS_WIDTH,
            max_height=MAX_CANVAS_HEIGHT,
        )
        fitted_w, fitted_h = compute_display_size(
            self.view_image.width,
            self.view_image.height,
            self.base_scale,
        )
        self.canvas_width = fitted_w
        self.canvas_height = fitted_h
        if hasattr(self, "info_image_size"):
            self.info_image_size.set(f"{self.view_image.width} x {self.view_image.height}")
        if hasattr(self, "canvas"):
            self.canvas.configure(width=self.canvas_width, height=self.canvas_height)

    def _apply_initial_selection(self, initial_crop_box: CropBox | None) -> None:
        if initial_crop_box and initial_crop_box.is_valid():
            self.selection_box = self._clamp_selection_to_image(initial_crop_box)
            return

        self._set_auto_trim_selection()

    def _set_auto_trim_selection(self, *, show_warning: bool = False) -> None:
        suggested = auto_trim_bbox(
            self.view_image,
            threshold=self.auto_trim_threshold,
            padding=self.auto_trim_padding,
        )
        if suggested and suggested.is_valid():
            self.selection_box = self._clamp_selection_to_image(suggested)
            return
        if show_warning:
            messagebox.showwarning("Auto Trim", "No content detected for auto trim.")

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        base_font = tkfont.nametofont("TkDefaultFont")
        base_font.configure(size=10, family="DejaVu Sans")

        style.configure("TFrame", padding=0)
        style.configure("TLabel", font=base_font)
        style.configure("TButton", font=base_font, padding=(10, 6))
        style.configure("Primary.TButton", foreground="#ffffff", background="#1f6feb")
        style.map("Primary.TButton", background=[("active", "#1158c7")])
        style.configure("Danger.TButton", foreground="#ffffff", background="#b62324")
        style.map("Danger.TButton", background=[("active", "#8f1c1d")])

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)

        left_panel = ttk.Frame(outer)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_panel.rowconfigure(0, weight=1)
        left_panel.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            left_panel,
            width=self.canvas_width,
            height=self.canvas_height,
            cursor="crosshair",
            highlightthickness=1,
            highlightbackground="#808080",
            background="#1c1c1c",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(left_panel)
        buttons.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for col in range(8):
            buttons.columnconfigure(col, weight=1)

        self.back_button = ttk.Button(buttons, text="Back", command=self.on_back)
        self.back_button.grid(row=0, column=0, padx=4, sticky="ew")
        if not self.allow_back:
            self.back_button.state(["disabled"])

        ttk.Button(buttons, text="Redo", command=self.on_redo).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="Rotate Left", command=self.on_rotate_left).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="Rotate Right", command=self.on_rotate_right).grid(
            row=0, column=3, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="Auto Trim", command=self.on_auto_trim).grid(
            row=0, column=4, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="Skip", command=self.on_skip).grid(
            row=0, column=5, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="Cancel", style="Danger.TButton", command=self.on_cancel).grid(
            row=0, column=6, padx=4, sticky="ew"
        )
        ttk.Button(buttons, text="OK", style="Primary.TButton", command=self.on_ok).grid(
            row=0, column=7, padx=4, sticky="ew"
        )

        right_panel = ttk.Frame(outer, padding=10)
        right_panel.grid(row=0, column=1, sticky="ns")

        ttk.Label(right_panel, text="Info", font=("DejaVu Sans", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        info_rows = [
            ("Image", self.info_image_size),
            ("Zoom", self.info_zoom),
            ("Selection", self.info_crop),
            ("Output", self.info_output),
            ("Progress", self.info_progress),
        ]
        for idx, (name, var) in enumerate(info_rows, start=1):
            ttk.Label(right_panel, text=f"{name}:").grid(row=idx * 2 - 1, column=0, sticky="w")
            ttk.Label(right_panel, textvariable=var, wraplength=260).grid(
                row=idx * 2,
                column=0,
                sticky="w",
                pady=(0, 8),
            )

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        self.canvas.bind("<Motion>", self.on_mouse_move)

        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)

        self.root.bind("<Return>", lambda _event: self.on_ok())
        self.root.bind("<Escape>", lambda _event: self.on_cancel())
        self.root.bind("<KeyPress-r>", lambda _event: self.on_redo())
        self.root.bind("<KeyPress-R>", lambda _event: self.on_redo())
        self.root.bind("<KeyPress-t>", lambda _event: self.on_auto_trim())
        self.root.bind("<KeyPress-T>", lambda _event: self.on_auto_trim())
        self.root.bind("<Control-Left>", lambda _event: self.on_rotate_left())
        self.root.bind("<Control-Right>", lambda _event: self.on_rotate_right())
        self.root.bind("<KeyPress-s>", lambda _event: self.on_skip())
        self.root.bind("<KeyPress-S>", lambda _event: self.on_skip())
        self.root.bind("<KeyPress-b>", lambda _event: self.on_back())
        self.root.bind("<KeyPress-B>", lambda _event: self.on_back())

        self.root.bind("<KeyPress-space>", self.on_space_press)
        self.root.bind("<KeyRelease-space>", self.on_space_release)

        self.root.bind("<Left>", lambda event: self.on_nudge(event, dx=-1, dy=0))
        self.root.bind("<Right>", lambda event: self.on_nudge(event, dx=1, dy=0))
        self.root.bind("<Up>", lambda event: self.on_nudge(event, dx=0, dy=-1))
        self.root.bind("<Down>", lambda event: self.on_nudge(event, dx=0, dy=1))

        self.root.bind("<Alt-Left>", lambda _event: self.on_resize_edge("left", -1))
        self.root.bind("<Alt-Right>", lambda _event: self.on_resize_edge("right", 1))
        self.root.bind("<Alt-Up>", lambda _event: self.on_resize_edge("top", -1))
        self.root.bind("<Alt-Down>", lambda _event: self.on_resize_edge("bottom", 1))

        self.root.bind("<KeyPress-bracketleft>", lambda _event: self.on_resize_box(-1))
        self.root.bind("<KeyPress-bracketright>", lambda _event: self.on_resize_box(1))

    def current_scale(self) -> float:
        return self.base_scale * self.zoom

    def _rerender_image(self) -> None:
        scale = self.current_scale()
        self.scaled_width, self.scaled_height = compute_display_size(
            self.view_image.width,
            self.view_image.height,
            scale,
        )
        self.display_image = self.view_image.resize(
            (self.scaled_width, self.scaled_height),
            resample=Image.Resampling.LANCZOS,
        )
        self.photo = ImageTk.PhotoImage(self.display_image)

    def _clamp_pan(self) -> None:
        if self.scaled_width <= self.canvas_width:
            self.pan_x = (self.canvas_width - self.scaled_width) / 2
        else:
            min_x = self.canvas_width - self.scaled_width
            self.pan_x = min(0, max(min_x, self.pan_x))

        if self.scaled_height <= self.canvas_height:
            self.pan_y = (self.canvas_height - self.scaled_height) / 2
        else:
            min_y = self.canvas_height - self.scaled_height
            self.pan_y = min(0, max(min_y, self.pan_y))

    def _image_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        scale = self.current_scale()
        return x * scale + self.pan_x, y * scale + self.pan_y

    def _canvas_to_image(self, x: float, y: float) -> tuple[float, float]:
        scale = self.current_scale()
        img_x = (x - self.pan_x) / scale
        img_y = (y - self.pan_y) / scale
        img_x = min(max(img_x, 0), self.view_image.width)
        img_y = min(max(img_y, 0), self.view_image.height)
        return img_x, img_y

    def _clamp_selection_to_image(self, box: CropBox) -> CropBox:
        normalized = box.normalized()
        left = int(min(max(normalized.left, 0), self.view_image.width))
        top = int(min(max(normalized.top, 0), self.view_image.height))
        right = int(min(max(normalized.right, 0), self.view_image.width))
        bottom = int(min(max(normalized.bottom, 0), self.view_image.height))
        return CropBox(left=left, top=top, right=right, bottom=bottom).normalized()

    def _redraw_scene(self) -> None:
        if self.photo is None:
            return

        if self.image_item_id is None:
            self.image_item_id = self.canvas.create_image(
                self.pan_x,
                self.pan_y,
                anchor="nw",
                image=self.photo,
            )
        else:
            self.canvas.itemconfig(self.image_item_id, image=self.photo)
            self.canvas.coords(self.image_item_id, self.pan_x, self.pan_y)

        self._redraw_selection()
        self._update_info_panel()

    def _redraw_selection(self) -> None:
        if self.selection_rect_id is not None:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None

        for overlay_id in self.overlay_ids:
            self.canvas.delete(overlay_id)
        self.overlay_ids.clear()

        if self.selection_box is None:
            return

        box = self.selection_box.normalized()
        x1, y1 = self._image_to_canvas(box.left, box.top)
        x2, y2 = self._image_to_canvas(box.right, box.bottom)

        self.overlay_ids.extend(
            [
                self.canvas.create_rectangle(
                    0,
                    0,
                    self.canvas_width,
                    y1,
                    fill="#000000",
                    stipple="gray50",
                    outline="",
                ),
                self.canvas.create_rectangle(
                    0,
                    y1,
                    x1,
                    y2,
                    fill="#000000",
                    stipple="gray50",
                    outline="",
                ),
                self.canvas.create_rectangle(
                    x2,
                    y1,
                    self.canvas_width,
                    y2,
                    fill="#000000",
                    stipple="gray50",
                    outline="",
                ),
                self.canvas.create_rectangle(
                    0,
                    y2,
                    self.canvas_width,
                    self.canvas_height,
                    fill="#000000",
                    stipple="gray50",
                    outline="",
                ),
            ]
        )

        self.selection_rect_id = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline="#00d084",
            width=2,
        )

    def _update_crosshair(self, canvas_x: int, canvas_y: int) -> None:
        if self.crosshair_x_id is None:
            self.crosshair_x_id = self.canvas.create_line(
                0,
                canvas_y,
                self.canvas_width,
                canvas_y,
                fill="#f2f2f2",
                dash=(2, 4),
            )
        else:
            self.canvas.coords(self.crosshair_x_id, 0, canvas_y, self.canvas_width, canvas_y)

        if self.crosshair_y_id is None:
            self.crosshair_y_id = self.canvas.create_line(
                canvas_x,
                0,
                canvas_x,
                self.canvas_height,
                fill="#f2f2f2",
                dash=(2, 4),
            )
        else:
            self.canvas.coords(self.crosshair_y_id, canvas_x, 0, canvas_x, self.canvas_height)

    def _update_info_panel(self) -> None:
        self.info_zoom.set(f"{self.zoom * 100:.0f}%")
        if self.selection_box is None:
            self.info_crop.set("x=0, y=0, w=0, h=0")
            return

        box = self.selection_box.normalized()
        self.info_crop.set(
            f"x={box.left}, y={box.top}, w={box.right - box.left}, h={box.bottom - box.top}"
        )

    def on_mouse_move(self, event: tk.Event) -> None:
        canvas_x = int(min(max(event.x, 0), self.canvas_width))
        canvas_y = int(min(max(event.y, 0), self.canvas_height))
        self._update_crosshair(canvas_x, canvas_y)

    def on_mouse_down(self, event: tk.Event) -> None:
        if self.space_held:
            self.on_pan_start(event)
            return

        img_x, img_y = self._canvas_to_image(event.x, event.y)
        self.drag_start_image_x = round(img_x)
        self.drag_start_image_y = round(img_y)
        self.selection_box = CropBox(
            left=self.drag_start_image_x,
            top=self.drag_start_image_y,
            right=self.drag_start_image_x,
            bottom=self.drag_start_image_y,
        )
        self._redraw_selection()
        self._update_info_panel()

    def on_mouse_drag(self, event: tk.Event) -> None:
        if self.is_panning:
            self.on_pan_drag(event)
            return

        if self.selection_box is None:
            return

        img_x, img_y = self._canvas_to_image(event.x, event.y)
        self.selection_box = CropBox(
            left=self.drag_start_image_x,
            top=self.drag_start_image_y,
            right=round(img_x),
            bottom=round(img_y),
        ).normalized()
        self._redraw_selection()
        self._update_info_panel()

    def on_mouse_up(self, _event: tk.Event) -> None:
        if self.is_panning:
            self.on_pan_end(_event)

    def on_pan_start(self, event: tk.Event) -> None:
        self.is_panning = True
        self.drag_start_canvas_x = event.x
        self.drag_start_canvas_y = event.y
        self.canvas.configure(cursor="fleur")

    def on_pan_drag(self, event: tk.Event) -> None:
        if not self.is_panning:
            return

        dx = event.x - self.drag_start_canvas_x
        dy = event.y - self.drag_start_canvas_y
        self.drag_start_canvas_x = event.x
        self.drag_start_canvas_y = event.y

        self.pan_x += dx
        self.pan_y += dy
        self._clamp_pan()
        self._redraw_scene()

    def on_pan_end(self, _event: tk.Event) -> None:
        self.is_panning = False
        self.canvas.configure(cursor="crosshair" if not self.space_held else "fleur")

    def on_mouse_wheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            direction = 1
        elif getattr(event, "num", None) == 5:
            direction = -1
        else:
            delta = getattr(event, "delta", 0)
            direction = 1 if delta > 0 else -1

        prev_scale = self.current_scale()
        new_zoom = self.zoom * (ZOOM_STEP if direction > 0 else 1 / ZOOM_STEP)
        self.zoom = min(MAX_ZOOM, max(MIN_ZOOM, new_zoom))

        if abs(self.current_scale() - prev_scale) < 1e-6:
            return

        mouse_x = min(max(event.x, 0), self.canvas_width)
        mouse_y = min(max(event.y, 0), self.canvas_height)
        factor = self.current_scale() / prev_scale

        self.pan_x = mouse_x - (mouse_x - self.pan_x) * factor
        self.pan_y = mouse_y - (mouse_y - self.pan_y) * factor

        self._rerender_image()
        self._clamp_pan()
        self._redraw_scene()

    def on_space_press(self, _event: tk.Event) -> None:
        self.space_held = True
        self.canvas.configure(cursor="fleur")

    def on_space_release(self, _event: tk.Event) -> None:
        self.space_held = False
        if not self.is_panning:
            self.canvas.configure(cursor="crosshair")

    def on_nudge(self, event: tk.Event, *, dx: int, dy: int) -> None:
        if self.selection_box is None:
            return

        state = event.state if isinstance(event.state, int) else 0
        if state & 0x4:
            return
        step = 10 if (state & 0x1) else 1
        box = self.selection_box.normalized()
        moved = CropBox(
            left=box.left + dx * step,
            top=box.top + dy * step,
            right=box.right + dx * step,
            bottom=box.bottom + dy * step,
        )
        self.selection_box = self._clamp_selection_to_image(moved)
        self._redraw_selection()
        self._update_info_panel()

    def on_resize_edge(self, edge: str, direction: int) -> None:
        if self.selection_box is None:
            return

        box = self.selection_box.normalized()
        step = 2
        if edge == "left":
            box = CropBox(box.left + direction * step, box.top, box.right, box.bottom)
        elif edge == "right":
            box = CropBox(box.left, box.top, box.right + direction * step, box.bottom)
        elif edge == "top":
            box = CropBox(box.left, box.top + direction * step, box.right, box.bottom)
        else:
            box = CropBox(box.left, box.top, box.right, box.bottom + direction * step)

        box = self._clamp_selection_to_image(box)
        if not box.is_valid():
            return

        self.selection_box = box
        self._redraw_selection()
        self._update_info_panel()

    def on_resize_box(self, direction: int) -> None:
        if self.selection_box is None:
            return

        box = self.selection_box.normalized()
        step = 3 * direction
        resized = CropBox(
            left=box.left - step,
            top=box.top - step,
            right=box.right + step,
            bottom=box.bottom + step,
        )
        resized = self._clamp_selection_to_image(resized)
        if not resized.is_valid():
            return

        self.selection_box = resized
        self._redraw_selection()
        self._update_info_panel()

    def _rotate_view(self, direction: Literal["left", "right"]) -> None:
        old_width = self.view_image.width
        old_height = self.view_image.height

        if direction == "left":
            self.view_image = self.view_image.transpose(Image.Transpose.ROTATE_90)
            self.rotation_deg = (self.rotation_deg + 90) % 360
            transformed = (
                rotate_crop_box(
                    self.selection_box,
                    width=old_width,
                    height=old_height,
                    rotation="left",
                )
                if self.selection_box is not None
                else None
            )
        else:
            self.view_image = self.view_image.transpose(Image.Transpose.ROTATE_270)
            self.rotation_deg = (self.rotation_deg - 90) % 360
            transformed = (
                rotate_crop_box(
                    self.selection_box,
                    width=old_width,
                    height=old_height,
                    rotation="right",
                )
                if self.selection_box is not None
                else None
            )

        self._update_window_title()
        self._update_view_geometry()

        if transformed is None:
            self._set_auto_trim_selection()
        else:
            self.selection_box = self._clamp_selection_to_image(transformed)

        self._rerender_image()
        self._clamp_pan()
        self._redraw_scene()

    def on_rotate_left(self) -> None:
        self._rotate_view("left")

    def on_rotate_right(self) -> None:
        self._rotate_view("right")

    def on_ok(self) -> None:
        if self.selection_box is None:
            messagebox.showwarning("No Selection", "Please drag to select a crop area.")
            return

        selected_box = self.selection_box.normalized()
        if not selected_box.is_valid():
            messagebox.showwarning("Invalid Selection", "Selected crop area is too small.")
            return

        save_cropped_image(
            self.view_image,
            selected_box,
            self.output_path,
            output_format=self.output_format,
            jpeg_quality=self.jpeg_quality,
        )
        self.result = CropResult(action="ok", output_path=self.output_path, crop_box=selected_box)
        self.root.destroy()

    def on_auto_trim(self) -> None:
        self._set_auto_trim_selection(show_warning=True)
        self._redraw_selection()
        self._update_info_panel()

    def on_redo(self) -> None:
        self.selection_box = None
        self._redraw_selection()
        self._update_info_panel()

    def on_skip(self) -> None:
        self.result = CropResult(action="skip", crop_box=self.selection_box)
        self.root.destroy()

    def on_cancel(self) -> None:
        self.result = CropResult(action="cancel", crop_box=self.selection_box)
        self.root.destroy()

    def on_back(self) -> None:
        if not self.allow_back:
            return
        self.result = CropResult(action="back", crop_box=self.selection_box)
        self.root.destroy()

    def run(self) -> CropResult:
        self.root.mainloop()
        return self.result


def run_crop(
    input_path: Path,
    output_path: Path,
    *,
    window_title: str | None = None,
    progress_text: str = "1/1",
    initial_crop_box: CropBox | None = None,
    allow_back: bool = False,
    auto_trim_threshold: int = 245,
    auto_trim_padding: int = 12,
    output_format: str | None = None,
    jpeg_quality: int = 90,
) -> CropResult:
    title = window_title or f"Crop Image: {input_path.name}"
    window = CropWindow(
        input_path=input_path,
        output_path=output_path,
        window_title=title,
        progress_text=progress_text,
        initial_crop_box=initial_crop_box,
        allow_back=allow_back,
        auto_trim_threshold=auto_trim_threshold,
        auto_trim_padding=auto_trim_padding,
        output_format=output_format,
        jpeg_quality=jpeg_quality,
    )
    return window.run()
