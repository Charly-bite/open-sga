import os
import signal
import wmi

c = wmi.WMI()
for process in c.Win32_Process():
    if (
        process.CommandLine
        and "sga_web" in process.CommandLine
        and ("app.py" in process.CommandLine or "run_production.py" in process.CommandLine)
    ):
        try:
            print(f"Killing {process.ProcessId}")
            os.kill(int(process.ProcessId), signal.SIGTERM)
        except Exception as e:
            print(e)
