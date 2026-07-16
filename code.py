"""
RIGOL Oscilloscope Control Panel
=================================
GUI (Tkinter) + Controller (PyVISA) พร้อม Auto-Simulation Mode
เมื่อไม่พบเครื่องจริงในระบบ

จุดที่ปรับปรุงล่าสุด
--------------------------
1. Horizontal offset และ Channel offset เปลี่ยนจาก Combobox -> Spinbox
   (มีลูกศรขึ้น/ลงให้ไล่ค่า และยังพิมพ์ค่าเองได้)
2. ขยายย่าน V/div ให้ครบตามลำดับ 1-2-5 ตั้งแต่ 500 µV/div ถึง 10 V/div
3. ขยายย่าน Time/div ให้ครบตามลำดับ 1-2-5 ตั้งแต่ 5 ns/div ถึง 500 s/div
4. ทุกปุ่ม / ทุก Combobox / ทุก Spinbox / ทุก Checkbutton
   มี "ฟังก์ชันของตัวเอง" ผูกกับ event (command / bind)
   และทุกฟังก์ชันจะ print บอกว่า "ผู้ใช้กด/เลือกอะไร" ออกทาง console
   เพื่อให้ debug และตรวจสอบการทำงานได้ง่าย
"""

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import pyvisa
import time


# =================================================================
# 0. ค่าคงที่: ย่านของ Time/div และ V/div (เรียงตามลำดับ 1-2-5)
# =================================================================
def _generate_1_2_5_series(units):
    """สร้างลิสต์ค่าตามลำดับ 1-2-5 จากรายการหน่วย [(unit_str, seconds_or_volts_per_unit, [multipliers]), ...]"""
    values = []
    for unit_str, multipliers in units:
        for m in multipliers:
            if m == int(m):
                values.append(f"{int(m)}.00{unit_str}")
            else:
                values.append(f"{m:.2f}{unit_str}")
    return values


# Time/div: 5 ns/div ... 500 s/div (ลำดับ 1-2-5)
TIME_DIV_VALUES = _generate_1_2_5_series([
    ("ns", [5, 10, 20, 50, 100, 200, 500]),
    ("µs", [1, 2, 5, 10, 20, 50, 100, 200, 500]),
    ("ms", [1, 2, 5, 10, 20, 50, 100, 200, 500]),
    ("s",  [1, 2, 5, 10, 20, 50, 100, 200, 500]),
])

# V/div: 500 µV/div ... 10 V/div (ลำดับ 1-2-5)
VOLT_DIV_VALUES = _generate_1_2_5_series([
    ("µV", [500]),
    ("mV", [1, 2, 5, 10, 20, 50, 100, 200, 500]),
    ("V",  [1, 2, 5, 10]),
])

# Horizontal offset: ช่วงค่าให้เลื่อนด้วย Spinbox (บวก/ลบรอบศูนย์)
H_OFFSET_VALUES = [
    "-500.00ms", "-100.00ms", "-10.00ms", "-1.00ms",
    "-100.00µs", "-10.00µs", "-1.00µs",
    "0.00s",
    "1.00µs", "10.00µs", "100.00µs",
    "1.00ms", "10.00ms", "100.00ms", "500.00ms",
]

# Channel offset: ช่วงค่าให้เลื่อนด้วย Spinbox (บวก/ลบรอบศูนย์)
CH_OFFSET_VALUES = [
    "-5.00V", "-2.00V", "-1.00V", "-500.00mV", "-200.00mV", "-100.00mV", "-50.00mV", "-10.00mV",
    "0.00V",
    "10.00mV", "50.00mV", "100.00mV", "200.00mV", "500.00mV", "1.00V", "2.00V", "5.00V",
]


# =================================================================
# 1. คลาส ScopeController (ระบบเชื่อมต่อ + Auto-Simulation)
# =================================================================
class ScopeController:
    """Simple SCPI controller for a USB oscilloscope (with Auto-Fallback Simulation)."""

    def __init__(self, backend="@py", timeout=5000):
        self.backend = backend
        self.timeout = timeout
        self.rm = None
        self.scope = None
        self.output_file = Path(__file__).parent / "live_display.png"
        self.simulation_mode = False
        self.mock_file = Path(__file__).parent / "mock_scope.png"

    def connect(self):
        try:
            self.rm = pyvisa.ResourceManager(self.backend)
            resources = self.rm.list_resources()
            for resource in resources:
                if resource.startswith("USB"):
                    self.scope = self.rm.open_resource(resource)
                    self.scope.timeout = self.timeout
                    self.simulation_mode = False
                    time.sleep(0.2)
                    print(f"Connected to real instrument: {resource}")
                    return
            raise RuntimeError("No USB instrument found in list.")
        except Exception as e:
            print(f"\n[Hardware Not Found]: {e}")
            print("-> Switching to SIMULATION MODE for GUI Designing...\n")
            self.simulation_mode = True
            if not self.mock_file.exists():
                self._create_dummy_image()

    def _create_dummy_image(self):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (800, 480), color='#1a1a1a')
            d = ImageDraw.Draw(img)
            d.text((320, 230), "[ SIMULATION MODE ]\n(Ready for GUI Design)", fill="#00ff00")
            img.save(self.mock_file)
        except ImportError:
            pass

    def disconnect(self):
        if self.simulation_mode:
            print("Closing Simulation.")
            return
        if self.scope is not None:
            self.scope.close()
            self.scope = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None

    def write(self, command):
        if self.simulation_mode:
            print(f"[Simulated Write]: {command}")
            return
        self.scope.write(command)

    def query(self, command, timeout=None):
        if self.simulation_mode:
            if "*IDN?" in command:
                return "RIGOL_MOCK_DEVICE_DS1000Z"
            return "0"
        if timeout is not None:
            self.scope.timeout = timeout
        return self.scope.query(command).strip()

    def run(self):
        self.write(":RUN")

    def stop(self):
        self.write(":STOP")

    def _read_ieee_block(self):
        header = self.scope.read_bytes(2)
        if header[0:1] != b"#":
            try:
                self.scope.read_bytes(2048)
            except Exception:
                pass
            raise RuntimeError(f"Unexpected IEEE header format: {header}")
        digits = int(header[1:2])
        length = int(self.scope.read_bytes(digits).decode())
        return self.scope.read_bytes(length)

    def capture_live_image(self):
        if self.simulation_mode:
            if self.mock_file.exists():
                self.output_file.write_bytes(self.mock_file.read_bytes())
                return self.output_file
            raise FileNotFoundError("Please place a 'mock_scope.png' in the script folder.")
        try:
            self.write(":DISPlay:SNAP?")
            png_data = self._read_ieee_block()
            if png_data.startswith(b"\x89PNG"):
                self.output_file.write_bytes(png_data)
                return self.output_file
            raise RuntimeError("Returned data is not a valid PNG image.")
        except Exception as e:
            try:
                self.scope.read_bytes(1024)
            except Exception:
                pass
            raise e

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# =================================================================
# Helper functions: แปลง string ที่มีหน่วย -> ตัวเลข (วินาที / โวลต์)
# =================================================================
def parse_time_to_seconds(text):
    """แปลงข้อความเวลาแบบมีหน่วย เช่น '2.00us' หรือ '2.00µs' -> 2e-6 (วินาที)"""
    text = text.strip()
    # รองรับทั้งสัญลักษณ์ µ (micro sign) และ μ (greek mu) รวมถึง 'us' แบบเดิม
    units = {
        "ps": 1e-12,
        "ns": 1e-9,
        "µs": 1e-6, "μs": 1e-6, "us": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
    }
    # ต้องเช็คหน่วยที่ยาวกว่าก่อน เพื่อไม่ให้ 's' ไปแมตช์ผิดตัว (เช่น 'ms' ลงท้ายด้วย 's' เช่นกัน)
    for unit in ("ps", "ns", "µs", "μs", "us", "ms", "s"):
        if text.endswith(unit):
            number_part = text[: -len(unit)]
            try:
                return float(number_part) * units[unit]
            except ValueError:
                return None
    return None


def parse_voltage_to_volts(text):
    """แปลงข้อความแรงดันแบบมีหน่วย เช่น '50.00mV' หรือ '500.00µV' -> โวลต์"""
    text = text.strip()
    units = {
        "µV": 1e-6, "μV": 1e-6,
        "mV": 1e-3,
        "V": 1.0,
    }
    for unit in ("µV", "μV", "mV", "V"):
        if text.endswith(unit):
            number_part = text[: -len(unit)]
            try:
                return float(number_part) * units[unit]
            except ValueError:
                return None
    return None


# =================================================================
# 2. คลาส GUI - ทุก widget มีฟังก์ชัน callback ของตัวเองที่ print แจ้งผล
# =================================================================
class LiveScopeApp:
    def __init__(self, root):
        self.stat = tk.StringVar()
        self.stat.set("Status : Run")
        self.root = root
        self.root.title("RIGOL Control Panel (Interactive GUI)")
        self.root.configure(bg="#f5f5f5")
        self.root.minsize(900, 620)  # ปรับ UI: กันหน้าต่างเล็กเกินไปจนบีบ layout

        self.controller = ScopeController()
        self.is_streaming = False

        # เก็บ widget ของแต่ละ channel ไว้ใช้อ้างอิงภายหลัง (ch -> dict ของ widgets)
        self.channel_widgets = {}

        style = ttk.Style()
        style.theme_use('clam')

        # -------------------------------------------------------------
        # [1] TOP FRAME - แถวด้านบนสุด (Info, Horizontal, Trigger)
        # -------------------------------------------------------------
        top_frame = tk.Frame(root, bg="#f5f5f5")
        top_frame.pack(side="top", fill="x", padx=15, pady=(15, 5))

        # 1.1 โซนซ้ายของด้านบน: Info & RUN/STOP
        info_area = tk.Frame(top_frame, bg="#f5f5f5")
        info_area.pack(side="left", anchor="n", padx=(0, 20))

        self.info_label = tk.Label(info_area, text="Connected:\nConnecting...",
                                    font=("Arial", 9, "bold"), bg="#f5f5f5", justify="left")
        self.info_label.pack(anchor="w")

        self.status_label = tk.Label(info_area, textvariable=self.stat,
                                      font=("Arial", 10, "bold"), bg="#f5f5f5", fg="#0a8a0a")
        self.status_label.pack(anchor="w", pady=5)

        btn_run_stop_frame = tk.Frame(info_area, bg="#f5f5f5")
        btn_run_stop_frame.pack(anchor="w")
        # ปุ่ม RUN -> ผูกกับ self.click_run
        self.btn_run = tk.Button(btn_run_stop_frame, text="▶ RUN", font=("Arial", 8),
                                  width=8, command=self.click_run)
        self.btn_run.pack(side="left", padx=(0, 5))
        # ปุ่ม STOP -> ผูกกับ self.click_stop
        self.btn_stop = tk.Button(btn_run_stop_frame, text="⏸ STOP", font=("Arial", 8),
                                   width=8, command=self.click_stop)
        self.btn_stop.pack(side="left")

        # 1.2 โซนกลางของด้านบน: Horizontal
        horiz_lf = tk.LabelFrame(top_frame, text="Horizontal", font=("Arial", 9, "bold"),
                                  bg="#f5f5f5", padx=10, pady=5)
        horiz_lf.pack(side="left", anchor="n", padx=10)

        # time/div -> เมื่อเลือกค่าใหม่ จะเรียก self.on_timebase_change (ครบย่าน 5ns - 500s ลำดับ 1-2-5)
        self.cb_timebase = self.create_dropdown_row(
            horiz_lf, "time/div", TIME_DIV_VALUES,
            width=10, on_select=self.on_timebase_change
        )
        # horizontal offset -> เปลี่ยนเป็น Spinbox, เมื่อเปลี่ยนค่า จะเรียก self.on_horizontal_offset_change
        self.sb_h_offset = self.create_spinbox_row(
            horiz_lf, "offset", H_OFFSET_VALUES,
            width=10, on_change=self.on_horizontal_offset_change,
            initial_value="0.00s"
        )

        # 1.3 โซนขวาของด้านบน: Trigger
        trigger_lf = tk.LabelFrame(top_frame, text="Trigger", font=("Arial", 9, "bold"),
                                    bg="#f5f5f5", padx=10, pady=5)
        trigger_lf.pack(side="left", anchor="n", padx=10)

        grid_trig = tk.Frame(trigger_lf, bg="#f5f5f5")
        grid_trig.pack()

        # --- source ---
        tk.Label(grid_trig, text="source", bg="#f5f5f5", anchor="w").grid(
            row=0, column=0, padx=5, pady=2, sticky="w")
        self.cb_trig_source = ttk.Combobox(grid_trig, values=["CH1", "CH2", "CH3", "CH4"], width=8)
        self.cb_trig_source.current(0)
        self.cb_trig_source.grid(row=0, column=1, padx=5, pady=2)
        # เมื่อเลือก source ใหม่ -> self.on_trigger_source_change
        self.cb_trig_source.bind("<<ComboboxSelected>>", self.on_trigger_source_change)

        # --- slope ---
        tk.Label(grid_trig, text="slope", bg="#f5f5f5", anchor="w").grid(
            row=1, column=0, padx=5, pady=2, sticky="w")
        self.cb_trig_slope = ttk.Combobox(grid_trig, values=["Rising", "Falling"], width=8)
        self.cb_trig_slope.current(0)
        self.cb_trig_slope.grid(row=1, column=1, padx=5, pady=2)
        # เมื่อเลือก slope ใหม่ -> self.on_trigger_slope_change
        self.cb_trig_slope.bind("<<ComboboxSelected>>", self.on_trigger_slope_change)

        # --- level (Entry) ---
        tk.Label(grid_trig, text="level", bg="#f5f5f5", anchor="w").grid(
            row=0, column=2, padx=5, pady=2, sticky="w")
        self.entry_trig_level = ttk.Entry(grid_trig, width=10)
        self.entry_trig_level.insert(0, "0.00V")
        self.entry_trig_level.grid(row=0, column=3, padx=5, pady=2)
        # กด Enter หรือคลิกออกจากช่อง -> self.on_trigger_level_change
        self.entry_trig_level.bind("<Return>", self.on_trigger_level_change)
        self.entry_trig_level.bind("<FocusOut>", self.on_trigger_level_change)

        # --- sweep ---
        tk.Label(grid_trig, text="sweep", bg="#f5f5f5", anchor="w").grid(
            row=1, column=2, padx=5, pady=2, sticky="w")
        self.cb_trig_sweep = ttk.Combobox(grid_trig, values=["Auto", "Normal", "Single"], width=8)
        self.cb_trig_sweep.current(0)
        self.cb_trig_sweep.grid(row=1, column=3, padx=5, pady=2)
        # เมื่อเลือก sweep ใหม่ -> self.on_trigger_sweep_change
        self.cb_trig_sweep.bind("<<ComboboxSelected>>", self.on_trigger_sweep_change)

        # -------------------------------------------------------------
        # [2] MIDDLE & LOWER SECTION
        # -------------------------------------------------------------
        main_frame = tk.Frame(root, bg="#f5f5f5")
        main_frame.pack(side="top", fill="both", expand=True, padx=15, pady=5)

        # 2.1 ฝั่งซ้าย: หน้าจอแสดงผล + ปุ่ม capture
        left_column = tk.Frame(main_frame, bg="#f5f5f5")
        left_column.pack(side="left", fill="both", expand=True)

        self.video_frame = tk.Frame(left_column, bg="black", bd=2, relief="sunken")
        self.video_frame.pack(side="top", fill="both", expand=True)

        self.display_label = tk.Label(
            self.video_frame, text="กำลังเชื่อมต่ออุปกรณ์...", bg="black", fg="white", font=("Arial", 12)
        )
        self.display_label.pack(fill="both", expand=True)

        bottom_left_bar = tk.Frame(left_column, bg="#f5f5f5")
        bottom_left_bar.pack(side="top", fill="x", pady=(10, 0))
        # ปุ่ม capture -> ผูกกับ self.capture
        self.btn_capture = tk.Button(bottom_left_bar, text="capture", width=15, command=self.capture)
        self.btn_capture.pack(side="left")
        # ป้ายบอกผลการ capture ล่าสุด (ปรับ UI เพิ่มเติม)
        self.capture_status_label = tk.Label(bottom_left_bar, text="", bg="#f5f5f5", font=("Arial", 8))
        self.capture_status_label.pack(side="left", padx=10)

        # 2.2 ฝั่งขวา: แผงช่องสัญญาณ CH1 - CH4
        right_column = tk.Frame(main_frame, bg="#f5f5f5")
        right_column.pack(side="right", fill="y", padx=(20, 0), anchor="n")

        self.create_channel_box(right_column, 1, "#e6c300", fg_text="#b38f00")
        self.create_channel_box(right_column, 2, "#0099ff")
        self.create_channel_box(right_column, 3, "#ff33aa")
        self.create_channel_box(right_column, 4, "#00bb44")

        # -------------------------------------------------------------
        # [3] BOTTOM BAR
        # -------------------------------------------------------------
        bottom_bar = tk.Frame(root, bg="#f5f5f5")
        bottom_bar.pack(side="bottom", fill="x", padx=15, pady=15)

        # ปุ่ม close -> ผูกกับ self.close_app
        self.btn_exit = tk.Button(bottom_bar, text="close", width=15, bg="#ff4d4d", fg="black",
                                   command=self.close_app)
        self.btn_exit.pack(side="right")

        self.init_connection()

    # -------------------------------------------------------------
    # ฟังก์ชันช่วยสร้าง Layout (Helper Functions)
    # -------------------------------------------------------------
    def create_dropdown_row(self, parent, label_text, values, width=8, on_select=None):
        """สร้างแถว Label + Combobox แล้วผูก event <<ComboboxSelected>> เข้ากับ on_select"""
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        lbl = tk.Label(row, text=label_text, width=8, bg="#f5f5f5", anchor="w")
        lbl.pack(side="left")
        cb = ttk.Combobox(row, values=values, width=width)
        cb.pack(side="right", padx=5)
        if values:
            cb.current(0)
        if on_select is not None:
            cb.bind("<<ComboboxSelected>>", on_select)
        return cb

    def create_spinbox_row(self, parent, label_text, values, width=8, on_change=None, initial_value=None):
        """สร้างแถว Label + Spinbox (ไล่ค่าจากลิสต์ values ด้วยลูกศรขึ้น/ลง หรือพิมพ์เองก็ได้)
        แล้วผูก event การเปลี่ยนค่าเข้ากับ on_change (เรียกตอนกดลูกศร / Enter / คลิกออกจากช่อง)"""
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        lbl = tk.Label(row, text=label_text, width=8, bg="#f5f5f5", anchor="w")
        lbl.pack(side="left")

        sb = tk.Spinbox(row, values=tuple(values), width=width, wrap=True,
                         command=lambda: on_change(None) if on_change else None)
        sb.pack(side="right", padx=5)

        # ตั้งค่าเริ่มต้น
        start_value = initial_value if initial_value in values else (values[0] if values else "")
        sb.delete(0, "end")
        sb.insert(0, start_value)

        if on_change is not None:
            # เรียกเมื่อพิมพ์ค่าเองแล้วกด Enter หรือคลิกออกจากช่อง
            sb.bind("<Return>", on_change)
            sb.bind("<FocusOut>", on_change)
        return sb

    def create_channel_box(self, parent, ch, border_color, fg_text=None):
        """สร้างบล็อกควบคุมของแต่ละ channel (CH1-CH4) พร้อมผูกฟังก์ชันให้ทุก widget"""
        text_color = fg_text if fg_text else border_color
        lf = tk.LabelFrame(
            parent, text=f"CH {ch}", font=("Arial", 9, "bold"),
            fg=text_color, bg="#f5f5f5", padx=8, pady=5, bd=2, relief="groove"
        )
        lf.pack(fill="x", pady=5)

        # --- display checkbox -> self.on_channel_display_toggle ---
        chk_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(
            lf, text="display", variable=chk_var, bg="#f5f5f5",
            activebackground="#f5f5f5", font=("Arial", 8),
            command=lambda ch=ch, var=chk_var: self.on_channel_display_toggle(ch, var)
        )
        chk.pack(anchor="w")

        # --- V/div -> self.on_channel_vdiv_change (ครบย่าน 500µV - 10V ลำดับ 1-2-5) ---
        cb_vdiv = self.create_channel_control_row(
            lf, "V/div", VOLT_DIV_VALUES,
            on_select=lambda e, ch=ch: self.on_channel_vdiv_change(ch, e.widget.get())
        )

        # --- offset -> เปลี่ยนเป็น Spinbox -> self.on_channel_offset_change ---
        sb_offset = self.create_channel_offset_spinbox_row(
            lf, "offset", CH_OFFSET_VALUES, ch=ch,
            initial_value="0.00V"
        )

        # --- coupling -> self.on_channel_coupling_change ---
        cb_coupling = self.create_channel_control_row(
            lf, "coupling", ["DC", "AC", "GND"],
            on_select=lambda e, ch=ch: self.on_channel_coupling_change(ch, e.widget.get())
        )

        # เก็บ widget ของ channel นี้ไว้ใช้อ้างอิงภายหลัง (ถ้าต้องการ)
        self.channel_widgets[ch] = {
            "display_var": chk_var,
            "vdiv": cb_vdiv,
            "offset": sb_offset,
            "coupling": cb_coupling,
        }

    def create_channel_control_row(self, parent, label_text, values, on_select=None):
        """จัดหน้าย่อยปุ่มควบคุม (Label + Combobox) และผูก event ให้ on_select"""
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=1)
        lbl = tk.Label(row, text=label_text, width=6, bg="#f5f5f5", font=("Arial", 8), anchor="w")
        lbl.pack(side="left")
        cb = ttk.Combobox(row, values=values, width=8, font=("Arial", 8))
        cb.pack(side="right", padx=(5, 0))
        if values:
            cb.current(0)
        if on_select is not None:
            cb.bind("<<ComboboxSelected>>", on_select)
        return cb

    def create_channel_offset_spinbox_row(self, parent, label_text, values, ch, initial_value=None):
        """จัดหน้าย่อยปุ่มควบคุม offset ของ channel เป็น Spinbox (แทน Combobox เดิม)
        ผูก event เข้ากับ self.on_channel_offset_change ของ channel นั้น ๆ"""
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=1)
        lbl = tk.Label(row, text=label_text, width=6, bg="#f5f5f5", font=("Arial", 8), anchor="w")
        lbl.pack(side="left")

        def _on_change(event=None, ch=ch):
            value = sb.get()
            self.on_channel_offset_change(ch, value)

        sb = tk.Spinbox(row, values=tuple(values), width=8, font=("Arial", 8), wrap=True,
                         command=lambda ch=ch: _on_change(None, ch))
        sb.pack(side="right", padx=(5, 0))

        start_value = initial_value if initial_value in values else (values[0] if values else "")
        sb.delete(0, "end")
        sb.insert(0, start_value)

        sb.bind("<Return>", lambda e, ch=ch: _on_change(e, ch))
        sb.bind("<FocusOut>", lambda e, ch=ch: _on_change(e, ch))
        return sb

    # -------------------------------------------------------------
    # CALLBACK: Horizontal
    # -------------------------------------------------------------
    def on_timebase_change(self, event):
        """เรียกเมื่อผู้ใช้เลือกค่า time/div ใหม่ จาก Combobox"""
        value = self.cb_timebase.get()
        print(f"[Horizontal] เลือก time/div = {value}")
        seconds = parse_time_to_seconds(value)
        if seconds is not None:
            self.controller.write(f":TIMebase:MAIN:SCALe {seconds}")
        else:
            print(f"  -> แปลงค่า '{value}' ไม่สำเร็จ")

    def on_horizontal_offset_change(self, event):
        """เรียกเมื่อผู้ใช้เปลี่ยนค่า horizontal offset ใหม่ จาก Spinbox (ลูกศร / พิมพ์เอง)"""
        value = self.sb_h_offset.get()
        print(f"[Horizontal] เลือก offset = {value}")
        seconds = parse_time_to_seconds(value)
        if seconds is not None:
            self.controller.write(f":TIMebase:MAIN:OFFSet {seconds}")
        else:
            print(f"  -> แปลงค่า '{value}' ไม่สำเร็จ")

    # -------------------------------------------------------------
    # CALLBACK: Trigger
    # -------------------------------------------------------------
    def on_trigger_source_change(self, event):
        """เรียกเมื่อผู้ใช้เลือก trigger source ใหม่ (CH1-CH4)"""
        value = self.cb_trig_source.get()
        ch = value[-1]
        print(f"[Trigger] เลือก source = {value}")
        print(f"command :TRIGger:EDGe:SOURce CHANnel{ch}")
        self.controller.write(f":TRIGger:EDGe:SOURce CHANnel{ch}")


    def on_trigger_slope_change(self, event):
        """เรียกเมื่อผู้ใช้เลือก trigger slope ใหม่ (Rising/Falling)"""
        value = self.cb_trig_slope.get()
        print(f"[Trigger] เลือก slope = {value}")
        scpi_value = "POSitive" if value == "Rising" else "NEGative"
        self.controller.write(f":TRIGger:EDGE:SLOPe {scpi_value}")

    def on_trigger_level_change(self, event):
        """เรียกเมื่อผู้ใช้พิมพ์ trigger level แล้วกด Enter หรือคลิกออกจากช่อง"""
        value = self.entry_trig_level.get()
        print(f"[Trigger] ตั้งค่า level = {value}")
        volts = parse_voltage_to_volts(value)
        if volts is not None:
            self.controller.write(f":TRIGger:EDGE:LEVel {volts}")
        else:
            print(f"  -> แปลงค่า '{value}' ไม่สำเร็จ (รูปแบบต้องเป็นเช่น 1.20V หรือ 500.00mV)")

    def on_trigger_sweep_change(self, event):
        """เรียกเมื่อผู้ใช้เลือก trigger sweep mode ใหม่ (Auto/Normal/Single)"""
        value = self.cb_trig_sweep.get()
        print(f"[Trigger] เลือก sweep = {value}")
        scpi_value = {"Auto": "AUTO", "Normal": "NORMal", "Single": "SINGle"}.get(value, "AUTO")
        self.controller.write(f":TRIGger:SWEep {scpi_value}")

    # -------------------------------------------------------------
    # CALLBACK: Channel (CH1-CH4)
    # -------------------------------------------------------------
    def on_channel_display_toggle(self, ch, var):
        """เรียกเมื่อผู้ใช้ติ๊ก/ยกเลิกติ๊ก checkbox 'display' ของ channel นั้น ๆ"""
        is_on = var.get()
        print(f"[CH{ch}] display = {'ON' if is_on else 'OFF'}")
        self.controller.write(f":CHANnel{ch}:DISPlay {'ON' if is_on else 'OFF'}")

    def on_channel_vdiv_change(self, ch, value):
        """เรียกเมื่อผู้ใช้เลือกค่า V/div ใหม่ของ channel นั้น ๆ"""
        print(f"[CH{ch}] เลือก V/div = {value}")
        volts = parse_voltage_to_volts(value)
        if volts is not None:
            self.controller.write(f":CHANnel{ch}:SCALe {volts}")
        else:
            print(f"  -> แปลงค่า '{value}' ไม่สำเร็จ")

    def on_channel_offset_change(self, ch, value):
        """เรียกเมื่อผู้ใช้เปลี่ยนค่า offset ใหม่ของ channel นั้น ๆ จาก Spinbox"""
        print(f"[CH{ch}] เลือก offset = {value}")
        volts = parse_voltage_to_volts(value)
        if volts is not None:
            self.controller.write(f":CHANnel{ch}:OFFSet {volts}")
        else:
            print(f"  -> แปลงค่า '{value}' ไม่สำเร็จ")

    def on_channel_coupling_change(self, ch, value):
        """เรียกเมื่อผู้ใช้เลือก coupling ใหม่ของ channel นั้น ๆ (DC/AC/GND)"""
        print(f"[CH{ch}] เลือก coupling = {value}")
        self.controller.write(f":CHANnel{ch}:COUPling {value}")

    # -------------------------------------------------------------
    # CALLBACK: ปุ่มหลัก (RUN / STOP / capture / close)
    # -------------------------------------------------------------
    def click_run(self):
        """เรียกเมื่อกดปุ่ม RUN"""
        print("[Button] กด RUN")
        try:
            self.controller.run()
            self.stat.set("Status : Run")
            self.status_label.config(fg="#0a8a0a")  # เขียว = กำลังรัน
        except Exception as e:
            print(f"Command Error: {e}")

    def click_stop(self):
        """เรียกเมื่อกดปุ่ม STOP"""
        print("[Button] กด STOP")
        try:
            self.controller.stop()
            self.stat.set("Status : Stop")
            self.status_label.config(fg="#cc0000")  # แดง = หยุดอยู่
        except Exception as e:
            print(f"Command Error: {e}")

    def capture(self):
        """เรียกเมื่อกดปุ่ม capture (บันทึกภาพหน้าจอปัจจุบันเป็นไฟล์)"""
        print("[Button] กด capture")
        try:
            img_path = self.controller.capture_live_image()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = img_path.parent / f"capture_{timestamp}.png"
            save_path.write_bytes(img_path.read_bytes())
            print(f"  -> บันทึกไฟล์แล้ว: {save_path}")
            self.capture_status_label.config(text=f"Saved: {save_path.name}")
        except Exception as e:
            print(f"Capture Error: {e}")
            self.capture_status_label.config(text=f"Error: {e}")

    def close_app(self):
        """เรียกเมื่อกดปุ่ม close (ปิดโปรแกรมและตัดการเชื่อมต่อ)"""
        print("[Button] กด close -> กำลังปิดระบบและเคลียร์พอร์ตเชื่อมต่อ...")
        self.is_streaming = False
        self.controller.disconnect()
        self.root.destroy()

    # -------------------------------------------------------------
    # พฤติกรรมพื้นฐานของโปรแกรม (เชื่อมต่อ / อัปเดตภาพ)
    # -------------------------------------------------------------
    def init_connection(self):
        try:
            self.controller.connect()
            time.sleep(0.5)
            try:
                idn = self.controller.query("*IDN?")
                self.info_label.config(text=f"Connected:\n{idn[:30]}...")
            except Exception:
                self.info_label.config(text="Connected:\nRIGOL Device")

            self.is_streaming = True
            self.update_loop()
        except Exception as e:
            self.display_label.config(text=f"การเชื่อมต่อล้มเหลว:\n{e}", fg="#ff4d4d")

    def update_loop(self):
        if self.is_streaming:
            try:
                img_path = self.controller.capture_live_image()
                self.img = tk.PhotoImage(file=str(img_path))
                self.display_label.config(image=self.img, text="")
                self.display_label.image = self.img
            except Exception as e:
                print(f"Stream Warning: {e} (Auto-recovering...)")

        self.root.after(700, self.update_loop)

    def command(self, command):
        """ฟังก์ชันสำรองสำหรับส่งคำสั่ง SCPI แบบอิสระ"""
        try:
            self.controller.write(command)
        except Exception as e:
            print(f"error: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LiveScopeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()