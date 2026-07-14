from datetime import datetime
from pathlib import Path
import tkinter as tk
import pyvisa
import time

# =================================================================
# 1. คลาส ScopeController (แก้ไขลบ .clear() ออกเพื่อไม่ให้ฟ้อง NSUP_OPER)
# =================================================================
class ScopeController:
    """Simple SCPI controller for a USB oscilloscope."""

    def __init__(self, backend="@py", timeout=5000):
        self.backend = backend
        self.timeout = timeout
        self.rm = None
        self.scope = None
        self.output_file = Path(__file__).parent / "live_display.png"

    def connect(self):
        """Connect to the first USB instrument."""
        self.rm = pyvisa.ResourceManager(self.backend)
        for resource in self.rm.list_resources():
            if resource.startswith("USB"):
                self.scope = self.rm.open_resource(resource)
                self.scope.timeout = self.timeout
                
                time.sleep(0.2)
                print(f"Connected to: {resource}")
                return
        raise RuntimeError("No USB instrument found.")

    def disconnect(self):
        """Close the instrument and VISA resource manager."""
        if self.scope is not None:
            self.scope.close()
            self.scope = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None

    def write(self, command):
        """Send a SCPI command."""
        self.scope.write(command)

    def query(self, command, timeout=None):
        """Send a SCPI query and return the response."""
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
            # หากหัวไฟล์เพี้ยน ใช้วิธีอ่านล้างข้อมูลไพเนารีในท่อทิ้งตรงๆ แทนการสั่ง .clear()
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
        try:
            self.write(":DISPlay:SNAP?")
            png_data = self._read_ieee_block()

            if png_data.startswith(b"\x89PNG"):
                self.output_file.write_bytes(png_data)
                return self.output_file
            raise RuntimeError("Returned data is not a valid PNG image.")
        except Exception as e:
            #  ถ้ามีปัญหา ให้ลองอ่านล้างบัฟเฟอร์แมนนวลสั้นๆ 1 ครั้ง
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
# 2. คลาส GUI ระบบ Auto-Layout
# =================================================================
class LiveScopeApp:
    def __init__(self, root):
        self.stat = tk.StringVar()
        self.stat.set("Status : Run")
        self.root = root
        self.root.title("RIGOL Live Monitor (Auto-Fit Display)")
        self.root.configure(bg="#f5f5f5") 

        self.controller = ScopeController()
        self.is_streaming = False

        # โครงสร้าง Layout แบบขยายอัตโนมัติ (Grid)
        root.grid_columnconfigure(0, minsize=10)
        root.grid_columnconfigure(1, minsize=10)
        root.grid_columnconfigure(2, minsize=10)

        self.video_frame = tk.Frame(root, bg="black")
        self.video_frame.grid(row=0, column=0, rowspan=5, padx=15, pady=15, sticky="nsew")

        self.display_label = tk.Label(
            self.video_frame, text="กำลังเชื่อมต่ออุปกรณ์...", bg="black", fg="white", font=("Arial", 12)
        )
        self.display_label.pack(fill="both", expand=True)

        self.info_label = tk.Label(
            root, text="Instrument Info", font=("Arial", 10, "bold"), bg="#f5f5f5"
        )
        self.info_label.grid(row=0, column=1, padx=2, pady=5, sticky="nw")

        self.status_label = tk.Label(root, textvariable=self.stat , font=("Arial", 10, "bold"), bg="#f5f5f5"
        )
        self.status_label.grid(row=0, column=2, padx=2, pady=5, sticky="nw")


        self.btn_run = tk.Button(
            root, text="▶ RUN", width=15, command=self.click_run
        )
        self.btn_run.grid(row=1, column=1, padx=2, pady=0, sticky="nw")

        self.btn_stop = tk.Button(
            root, text="⏸ STOP", width=15, command=self.click_stop
        )
        self.btn_stop.grid(row=1, column=2, padx=2, pady=0, sticky="nw")

        self.btn_exit = tk.Button(
            root, text="close", width=15, bg="#ff4d4d", fg="black", command=self.close_app
        )
        self.btn_exit.grid(row=4, column=1, padx=20, pady=20, sticky="nw")

        self.btn_capture = tk.Button(
            root, text="capture" , width=15 ,command = self.capture
        )
        self.btn_capture.grid(row=3, column=1, padx=20, pady=20, sticky="nw")

        self.init_connection()

    def init_connection(self):
        try:
            self.controller.connect()
            time.sleep(0.5) 
            
            try:
                idn = self.controller.get_idn()
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

                # อัปเดตภาพขึ้นหน้าจอหลัก
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
            # ดึงภาพจากเครื่อง (ได้ไฟล์ live_display.png)
            img_path = self.controller.capture_live_image()

            # สร้างชื่อไฟล์จากวันเวลา
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = img_path.parent / f"capture_{timestamp}.png"

            # คัดลอกไฟล์
            save_path.write_bytes(img_path.read_bytes())

            print(f"Saved: {save_path}")

        except Exception as e:
            print(f"Capture Error: {e}")

    def command(self,command):
        try:
            self.controller.write(command)
        except:
            print("error")

if __name__ == "__main__":
    root = tk.Tk()
    app = LiveScopeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()