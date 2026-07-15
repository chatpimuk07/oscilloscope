# RIGOL Oscilloscope Live Monitor & Control Panel

A professional Python-based desktop application for remote monitoring, real-time control, and parameter configuration of RIGOL Oscilloscopes (specifically the DS1000Z series) via USB interfaces using SCPI commands.

Featuring an **interactive GUI built with Tkinter** and a backend powered by **PyVISA**, the system also implements an **Auto-Fallback Simulation Mode** so that developers can test and refine the UI even when physical hardware is not connected.

---

## 🚀 Key Features

* **Real-Time Live Stream Display:** High-resolution waveform monitoring with automated UI updates (700 ms polling intervals).
* **Extended Dynamic Ranges (1-2-5 Step Series):**
  * **Horizontal Timebase:** Broad spectrum ranging from **5 ns/div up to 500 s/div**.
  * **Vertical Scale (V/div):** Dynamic range span from **500 µV/div up to 10 V/div** for all 4 channels.
* **Precise Offset Fine-Tuning:** Uses tactile **Spinbox** controls for both Horizontal and Channel offsets instead of standard dropdowns, allowing for quick increments/decrements and direct manual typing.
* **Full Multi-Channel Capabilities:** Individual controls for **CH1 - CH4** with dedicated toggle displays, scales, offsets, and input coupling settings (AC/DC/GND).
* **Comprehensive Edge Trigger Settings:** Full control over trigger source, slope types (Rising/Falling), level thresholds, and sweep modes (Auto/Normal/Single).
* **One-Click Screen Capture:** Dedicated snapshot functionality that auto-saves high-resolution PNG screen contents directly to your project directory with precise timestamp file-naming.
* **Console Debug Logging (Traceability):** Every single widget, button, combo-box, and spinbox interaction is bound to its own event-driven callback function, producing real-time tracing logs on the terminal console for seamless testing.
* **Robust SCPI Transmission:** Custom IEEE-488.2 binary block parser handles raw stream data safely, avoiding standard `NSUP_OPER` timeout buffer errors.

---

## 🛠 Prerequisites

### 1. VISA Driver
Ensure a valid VISA library is installed on the host operating system:
* **Windows:** National Instruments NI-VISA or Keysight IO Libraries Suite.
* **macOS/Linux:** Homebrew/system packages or use the pure-Python pyvisa-py backend.

### 2. Dependencies
Install the required library packages using `pip`:
```bash
pip install pyvisa pyvisa-py Pillow
