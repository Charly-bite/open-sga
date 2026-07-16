import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import time


class SGAVisorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Panel de Control SGA (Visor de Puertos y Watchdog)")
        self.root.geometry("750x550")

        # Styles
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10), padding=5)

        # Procesos Frame
        frame_proc = tk.LabelFrame(
            root,
            text="Servidores y Rogue Process en Puerto 5000",
            padx=10,
            pady=10,
            font=("Arial", 11, "bold"),
        )
        frame_proc.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            frame_proc, columns=("PID", "Name", "Details"), show="headings", height=8
        )
        self.tree.heading("PID", text="PID")
        self.tree.heading("Name", text="Nombre (Proceso)")
        self.tree.heading("Details", text="Detalles (Línea de comando)")
        self.tree.column("PID", width=80, anchor="center")
        self.tree.column("Name", width=150)
        self.tree.column("Details", width=450)
        self.tree.pack(fill="both", expand=True, pady=5)

        btn_frame = tk.Frame(frame_proc)
        btn_frame.pack(fill="x", pady=5)

        tk.Button(
            btn_frame, text="Refrescar Lista", command=self.refresh_procs, bg="#f0f0f0"
        ).pack(side="left", padx=5)
        tk.Button(
            btn_frame,
            text="Terminar Proceso Seleccionado",
            command=self.kill_selected,
            bg="#ffd966",
        ).pack(side="left", padx=5)
        tk.Button(
            btn_frame,
            text="Liberar todo el Puerto 5000 (Purga Total)",
            command=self.kill_all_5000,
            bg="#ff4d4d",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side="right", padx=5)

        # Watchdog Frame
        frame_wd = tk.LabelFrame(
            root,
            text="Control del Watchdog",
            padx=10,
            pady=10,
            font=("Arial", 11, "bold"),
        )
        frame_wd.pack(fill="x", padx=10, pady=10)

        self.wd_status = tk.StringVar()
        self.wd_status.set("Estado del Watchdog: Desconocido")

        self.status_label = tk.Label(
            frame_wd, textvariable=self.wd_status, font=("Arial", 12, "bold")
        )
        self.status_label.pack(pady=10)

        wd_btn_frame = tk.Frame(frame_wd)
        wd_btn_frame.pack(fill="x", pady=5)
        tk.Button(
            wd_btn_frame,
            text="Iniciar Watchdog",
            command=self.start_watchdog,
            bg="#99ff99",
            font=("Arial", 10, "bold"),
        ).pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(
            wd_btn_frame,
            text="Detener Watchdog",
            command=self.stop_watchdog,
            bg="#ff9999",
            font=("Arial", 10, "bold"),
        ).pack(side="left", fill="x", expand=True, padx=10)

        self.refresh_procs()
        self.check_watchdog_status()

    def get_port_5000_pids(self):
        try:
            # netstat -aon | findstr ":5000 "
            output = subprocess.check_output(
                'netstat -aon | findstr ":5000 "', shell=True
            ).decode(errors="ignore")
            pids = set()
            for line in output.split("\n"):
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid != "0":
                        pids.add(pid)
            return list(pids)
        except subprocess.CalledProcessError:
            return []

    def get_process_info(self, pid):
        try:
            cmd = (
                f'wmic process where processid="{pid}" get name,commandline /format:csv'
            )
            output = (
                subprocess.check_output(cmd, shell=True).decode(errors="ignore").strip()
            )
            lines = [line for line in output.split("\n") if line.strip()]
            if len(lines) > 1:
                parts = lines[1].strip().split(",")
                if len(parts) >= 3:
                    return parts[2], parts[1]  # Name, CommandLine
                elif len(parts) == 2:
                    return parts[1], ""
            return "Unknown", ""
        except Exception:
            return "Unknown", ""

    def refresh_procs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        pids = self.get_port_5000_pids()
        if not pids:
            self.tree.insert(
                "", "end", values=("-", "Ninguno", "Puerto 5000 libre. Todo 정상.")
            )
            return

        for pid in pids:
            name, cmd = self.get_process_info(pid)
            cmd_display = cmd[:100] + "..." if len(cmd) > 100 else cmd
            self.tree.insert("", "end", values=(pid, name, cmd_display))

    def kill_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        pid = item["values"][0]
        if pid == "-":
            return

        try:
            os.system(f"taskkill /F /PID {pid} /T")
            time.sleep(1)
            self.refresh_procs()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def kill_all_5000(self):
        answer = messagebox.askyesno(
            "Confirmar",
            "¿Seguro que quieres matar todos los procesos en el puerto 5000?",
        )
        if not answer:
            return

        pids = self.get_port_5000_pids()
        for pid in pids:
            os.system(f"taskkill /F /PID {pid} /T")
        time.sleep(1)
        self.refresh_procs()

    def check_watchdog_status(self):
        try:
            cmd = "wmic process where \"commandline like '%watchdog.py%' and name!='wmic.exe'\" get processid"
            output = (
                subprocess.check_output(cmd, shell=True).decode(errors="ignore").strip()
            )
            lines = [
                line
                for line in output.split("\n")
                if line.strip() and line.strip().isdigit()
            ]

            if len(lines) > 0:
                self.wd_status.set("Estado del Watchdog: CORRIENDO (Activo)")
                self.status_label.config(fg="green")
            else:
                self.wd_status.set("Estado del Watchdog: DETENIDO")
                self.status_label.config(fg="red")
        except Exception:
            self.wd_status.set("Estado del Watchdog: DETENIDO")
            self.status_label.config(fg="red")

        self.root.after(3000, self.check_watchdog_status)  # Auto repite cada 3 sec

    def start_watchdog(self):
        try:
            cwd = r"C:\Users\QB_DESARROLLO\Desktop\DEVELOPMENT"
            os.system(f'start "" /d "{cwd}" cmd.exe /c "start_watchdog.bat"')
            time.sleep(1)
            self.check_watchdog_status()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_watchdog(self):
        try:
            # Primero mata el batch script (cmd.exe) que contiene el ciclo infinito
            cmd_batch = "wmic process where \"commandline like '%start_watchdog%' and name!='wmic.exe'\" call terminate"
            subprocess.call(
                cmd_batch,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Mata el proceso de Python que corre watchdog.py
            cmd_py = "wmic process where \"commandline like '%watchdog.py%' and name!='wmic.exe'\" call terminate"
            subprocess.call(
                cmd_py, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # (Por si acaso quedó la ventana abierta) Mata la ventana de CMD que se llama "SGA Server Watchdog"
            os.system(
                'taskkill /F /FI "WINDOWTITLE eq SGA Server Watchdog*" /T >nul 2>&1'
            )
            time.sleep(1)
            self.check_watchdog_status()
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = SGAVisorApp(root)
    root.mainloop()
