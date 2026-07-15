# RIGOL Oscilloscope Live Monitor

A professional Python-based desktop application for remote monitoring and control of RIGOL Oscilloscopes via USB interfaces using SCPI commands.

## Key Features
*   **Live Stream Display:** Real-time waveform monitoring with automated UI updates (700 ms intervals).
*   **Instrument Control:** Dedicated remote buttons for `▶ RUN` and `⏸ STOP` acquisition modes.
*   **Screen Capture:** One-click high-resolution PNG snapshot saving with automated timestamp naming.
*   **Robust Architecture:** Custom manual IEEE binary block parsing to eliminate standard `NSUP_OPER` buffer errors.

## Prerequisites
1.  **VISA Driver:** Ensure NI-VISA or Keysight IO Libraries Suite is installed on the host system.
2.  **Dependencies:** Install the required Python packages via pip:
    ```bash
    pip install pyvisa pyvisa-py
    ```

## Installation & Usage
1. Connect the oscilloscope to the PC via USB and power it on.
2. Run the application script:
   ```bash
   python main.py
