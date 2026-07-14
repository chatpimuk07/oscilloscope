from datetime import datetime
from pathlib import Path
import tkinter as tk
import pyvisa
import time

# =================================================================
# 1. คลาส ScopeController (ระบบเชื่อมต่อ และ Auto-Simulation)
# =================================================================
class ScopeController:
    """Simple SCPI controller for a USB oscilloscope (with Auto-Fallback Simulation)."""

    def __init__(self, backend="@py", timeout=5000):
        self.backend = backend
        self.timeout = timeout
        self.rm = None
        self.scope = None
        self.output_file = Path(__file__).parent / "live_display.png"
        
        # สถานะโหมดจำลอง (จะเปลี่ยนเป็น True อัตโนมัติถ้าไม่เจอเครื่องจริง)
        self.simulation_mode = False 
        self.mock_file = Path(__file__).parent / "mock_scope.png"

    def connect(self):
        """Connect to the first USB instrument. If not found, switch to simulation mode."""
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
            
            # สร้างรูปจำลองพื้นหลังสีดำขึ้นมาด่วน หากในโฟลเดอร์ยังไม่มีไฟล์รูปภาพ
            if not self.mock_file.exists():
                self._create_dummy_image()

    def _create_dummy_image(self):
        """สร้างไฟล์ภาพจำลองขนาด 800x480 ในกรณีที่ไม่ได้ต่อสโคปจริง"""
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (800, 480), color='#1a1a1a')
            d = ImageDraw.Draw(img)
            d.text((320, 230), "[ SIMULATION MODE ]\n(Ready for GUI Design)", fill="#00ff00")
            img.save(self.mock_file)
        except ImportError:
            pass

    def disconnect(self):
        """Close the instrument and VISA resource manager."""
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
        """Send a SCPI command."""
        if self.simulation_mode:
            print(f"[Simulated Write]: {command}")
            return
        self.scope.write(command)

    def query(self, command, timeout=None):
        """Send a SCPI query and return the response."""
        if self.simulation_mode:
            if "*IDN?" in command:
                return "RIGOL_MOCK_DEVICE_DS1000Z"
            return "0"
            
        if timeout is not None:
            self.scope.timeout = timeout
        return self.scope.query(command).strip()

    def run(self):
        """Start waveform acquisition."""
        self.write(":RUN")

    def stop(self):
        """Stop waveform acquisition."""
        self.write(":STOP")

    def _read_ieee_block(self):
        """อ่านข้อมูลไบนารีบล็อกจากเครื่องสโคปพร้อมระบบเคลียร์ขยะแมนนวล"""
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
        """ส่งคำสั่งดึงภาพและบันทึกไฟล์ภาพชั่วคราว"""
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
# 2. คลาส GUI ระบบ Pack Layout (Auto-Fit ไร้ Grid)
# =================================================================
class LiveScopeApp:
    def __init__(self, root):
        self.stat = tk.StringVar()
        self.stat.set("Status : Run")
        self.root = root
        self.root.title("RIGOL Live Monitor (Pack Layout)")
        self.root.configure(bg="#f5f5f5") 

        self.controller = ScopeController()
        self.is_streaming = False

        # -------------------------------------------------------------
        # [จัดเลย์เอาต์หลัก] ฝั่งซ้าย: แสดงภาพสโคป
        # -------------------------------------------------------------
        self.video_frame = tk.Frame(root, bg="black")
        self.video_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        self.display_label = tk.Label(
            self.video_frame, text="กำลังเชื่อมต่ออุปกรณ์...", bg="black", fg="white", font=("Arial", 12)
        )
        self.display_label.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # [จัดเลย์เอาต์หลัก] ฝั่งขวา: แผงควบคุมปุ่มกดทั้งหมด
        # -------------------------------------------------------------
        self.control_frame = tk.Frame(root, bg="#f5f5f5")
        self.control_frame.pack(side="right", fill="y", padx=15, pady=15, anchor="n")

        # ส่วนแสดงข้อมูลข้อความ (Text Info)
        self.info_label = tk.Label(
            self.control_frame, text="Instrument Info", font=("Arial", 10, "bold"), bg="#f5f5f5", justify="left"
        )
        self.info_label.pack(anchor="w", pady=(0, 5))

        self.status_label = tk.Label(
            self.control_frame, textvariable=self.stat, font=("Arial", 10, "bold"), bg="#f5f5f5"
        )
        self.status_label.pack(anchor="w", pady=(0, 15))

        # ส่วนของกลุ่มปุ่มย่อย (เรียง RUN / STOP ซ้าย-ขวาคู่กัน)
        self.btn_sub_frame = tk.Frame(self.control_frame, bg="#f5f5f5")
        self.btn_sub_frame.pack(anchor="w", pady=5)

        self.btn_run = tk.Button(self.btn_sub_frame, text="▶ RUN", width=10, command=self.click_run)
        self.btn_run.pack(side="left", padx=(0, 5))

        self.btn_stop = tk.Button(self.btn_sub_frame, text="⏸ STOP", width=10, command=self.click_stop)
        self.btn_stop.pack(side="left")

        # ปุ่มฟังก์ชันเรียงตัวลงมาด้านล่าง
        self.btn_capture = tk.Button(self.control_frame, text="📷 capture", width=22, command=self.capture)
        self.btn_capture.pack(anchor="w", pady=10)

        # ปุ่ม Close ถูกดันไปไว้ท้ายสุดของแผงควบคุม
        self.btn_exit = tk.Button(
            self.control_frame, text="close", width=22, bg="#ff4d4d", fg="black", command=self.close_app
        )
        self.btn_exit.pack(side="bottom", pady=(20, 0))

        self.init_connection()

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
        """ลูปดึงภาพสดมาแสดงผล"""
        if self.is_streaming:
            try:
                img_path = self.controller.capture_live_image()
                self.img = tk.PhotoImage(file=str(img_path))

                self.display_label.config(image=self.img, text="")
                self.display_label.image = self.img 

            except Exception as e:
                print(f"Stream Warning: {e} (Auto-recovering...)")

            self.root.after(700, self.update_loop)

    def click_run(self):
        try:
            self.controller.run()
            self.stat.set("Status : Run")
        except Exception as e:
            print(f"Command Error: {e}")

    def click_stop(self):
        try:
            self.controller.stop()
            self.stat.set("Status : Stop")
        except Exception as e:
            print(f"Command Error: {e}")

    def close_app(self):
        print("\nกำลังปิดระบบและเคลียร์พอร์ตเชื่อมต่อ...")
        self.is_streaming = False  
        self.controller.disconnect()  
        self.root.destroy()

    def capture(self):
        """บันทึกภาพหน้าจอเป็นไฟล์ใหม่พร้อมเวลาปัจจุบัน"""
        try:
            img_path = self.controller.capture_live_image()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = img_path.parent / f"capture_{timestamp}.png"
            save_path.write_bytes(img_path.read_bytes())
            print(f"Saved: {save_path}")
        except Exception as e:
            print(f"Capture Error: {e}")

    def command(self, command):
        try:
            self.controller.write(command)
        except:
            print("error")

if __name__ == "__main__":
    root = tk.Tk()
    app = LiveScopeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()