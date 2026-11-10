# GUI scenario and configuration manager
from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, Tuple


CONFIG_PATH = Path(__file__).parent / "config.json"
MAIN_SCRIPT = Path(__file__).parent / "main.py"

SCENARIO_PRESETS: Dict[str, Dict[str, Any]] = {
    "1. Balanced Swarm (Default)": {
        "description": "Standard balance between flocking cohesion, obstacle avoidance, and medium radio range.",
        "swarm": {"num_agents": 50, "max_speed": 3.2, "min_speed": 1.6, "max_force": 0.14},
        "flocking_radii": {"perception_radius": 68.0, "separation_radius": 28.0},
        "weights": {
            "separation": 2.10,
            "alignment": 1.05,
            "cohesion": 0.85,
            "obstacle_avoidance": 3.40,
            "wander": 0.20,
        },
        "dtn_network": {
            "comm_radius": 80.0,
            "bandwidth_rate": 0.035,
            "require_line_of_sight": True,
        },
    },
    "2. High-Cohesion Swarm (Compact Flock)": {
        "description": "High cohesion and strong alignment: agents move in tight, dense clusters.",
        "swarm": {"num_agents": 50, "max_speed": 3.4, "min_speed": 1.8, "max_force": 0.15},
        "flocking_radii": {"perception_radius": 90.0, "separation_radius": 24.0},
        "weights": {
            "separation": 1.60,
            "alignment": 2.20,
            "cohesion": 2.00,
            "obstacle_avoidance": 3.60,
            "wander": 0.08,
        },
        "dtn_network": {
            "comm_radius": 80.0,
            "bandwidth_rate": 0.035,
            "require_line_of_sight": True,
        },
    },
    "3. Dispersed Exploration (Random Gas)": {
        "description": "High separation and stochastic exploration: agents cover the entire arena uniformly.",
        "swarm": {"num_agents": 50, "max_speed": 3.6, "min_speed": 2.0, "max_force": 0.15},
        "flocking_radii": {"perception_radius": 60.0, "separation_radius": 42.0},
        "weights": {
            "separation": 3.20,
            "alignment": 0.15,
            "cohesion": 0.10,
            "obstacle_avoidance": 3.40,
            "wander": 0.80,
        },
        "dtn_network": {
            "comm_radius": 75.0,
            "bandwidth_rate": 0.035,
            "require_line_of_sight": True,
        },
    },
    "4. Short-Range DTN (Store-Carry-Forward)": {
        "description": "Reduced radio radius (45 px): agents physically transport data across disconnected gaps.",
        "swarm": {"num_agents": 50, "max_speed": 3.4, "min_speed": 1.8, "max_force": 0.14},
        "flocking_radii": {"perception_radius": 68.0, "separation_radius": 28.0},
        "weights": {
            "separation": 2.10,
            "alignment": 1.00,
            "cohesion": 0.75,
            "obstacle_avoidance": 3.40,
            "wander": 0.35,
        },
        "dtn_network": {
            "comm_radius": 45.0,
            "bandwidth_rate": 0.045,
            "require_line_of_sight": True,
        },
    },
    "5. Limited Bandwidth (Large File)": {
        "description": "Slow transfer rate (0.008): multiple peer encounters are required to download 100%.",
        "swarm": {"num_agents": 50, "max_speed": 3.2, "min_speed": 1.6, "max_force": 0.14},
        "flocking_radii": {"perception_radius": 68.0, "separation_radius": 28.0},
        "weights": {
            "separation": 2.10,
            "alignment": 1.05,
            "cohesion": 0.85,
            "obstacle_avoidance": 3.40,
            "wander": 0.25,
        },
        "dtn_network": {
            "comm_radius": 80.0,
            "bandwidth_rate": 0.008,
            "require_line_of_sight": True,
        },
    },
}


class ConfiguratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Boids & DTN Simulation Settings")
        self.root.geometry("620x660")

        self.current_data: Dict[str, Any] = self._load_json()
        self.sliders: Dict[str, Tuple[tk.DoubleVar, ttk.Label, str]] = {}

        self._build_ui()
        self._populate_from_data(self.current_data)

    def _load_json(self) -> Dict[str, Any]:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text="Simulation Parameters (config.json)",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        preset_frame = ttk.LabelFrame(
            main_frame, text=" Predefined Scenarios ", padding=8
        )
        preset_frame.pack(fill=tk.X, pady=4)

        self.preset_var = tk.StringVar(value=list(SCENARIO_PRESETS.keys())[0])
        preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(SCENARIO_PRESETS.keys()),
            state="readonly",
        )
        preset_combo.pack(fill=tk.X, pady=(0, 4))
        preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        self.preset_desc_lbl = ttk.Label(
            preset_frame,
            text=SCENARIO_PRESETS[self.preset_var.get()]["description"],
            wraplength=580,
        )
        self.preset_desc_lbl.pack(anchor=tk.W)

        swarm_frame = ttk.LabelFrame(
            main_frame, text=" 1. Swarm Population & Kinematics ", padding=8
        )
        swarm_frame.pack(fill=tk.X, pady=4)
        self._add_slider(swarm_frame, "num_agents", "Number of agents:", 10, 150, 1, "{:.0f}")
        self._add_slider(swarm_frame, "max_speed", "Maximum speed:", 1.0, 6.0, 0.1, "{:.1f}")
        self._add_slider(swarm_frame, "perception_radius", "Perception radius (px):", 30, 150, 1, "{:.0f}")
        self._add_slider(swarm_frame, "separation_radius", "Separation radius (px):", 12, 70, 1, "{:.0f}")

        weights_frame = ttk.LabelFrame(
            main_frame, text=" 2. Flocking Weights (Reynolds Rules) ", padding=8
        )
        weights_frame.pack(fill=tk.X, pady=4)
        self._add_slider(weights_frame, "separation", "Separation weight:", 0.0, 5.0, 0.05, "{:.2f}")
        self._add_slider(weights_frame, "alignment", "Alignment weight:", 0.0, 4.0, 0.05, "{:.2f}")
        self._add_slider(weights_frame, "cohesion", "Cohesion weight:", 0.0, 4.0, 0.05, "{:.2f}")
        self._add_slider(weights_frame, "obstacle_avoidance", "Obstacle avoidance weight:", 0.5, 6.0, 0.1, "{:.2f}")
        self._add_slider(weights_frame, "wander", "Wander weight:", 0.0, 2.0, 0.05, "{:.2f}")

        dtn_frame = ttk.LabelFrame(
            main_frame, text=" 3. Ad-Hoc Network (DTN) ", padding=8
        )
        dtn_frame.pack(fill=tk.X, pady=4)
        self._add_slider(dtn_frame, "comm_radius", "Radio range (px):", 25, 160, 1, "{:.0f}")
        self._add_slider(dtn_frame, "bandwidth_rate", "Download rate:", 0.002, 0.10, 0.002, "{:.3f}")

        self.los_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            dtn_frame,
            text="Solid obstacles block radio waves (Line of Sight)",
            variable=self.los_var,
        ).pack(anchor=tk.W, pady=(4, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(
            btn_frame,
            text="Save to config.json (Press [C] in simulation)",
            command=self.save_config,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        ttk.Button(
            btn_frame,
            text="Save & Launch Simulation",
            command=self.save_and_launch,
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def _add_slider(
        self,
        parent: ttk.Widget,
        key: str,
        label_text: str,
        min_val: float,
        max_val: float,
        resolution: float,
        fmt: str,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)

        ttk.Label(row, text=label_text, width=30).pack(side=tk.LEFT)
        val_lbl = ttk.Label(row, text="0", width=8)
        val_lbl.pack(side=tk.RIGHT)

        var = tk.DoubleVar(value=min_val)

        def on_change(_: Any = None) -> None:
            val_lbl.configure(text=fmt.format(var.get()))

        scale = tk.Scale(
            row,
            variable=var,
            from_=min_val,
            to=max_val,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            showvalue=False,
            command=on_change,
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.sliders[key] = (var, val_lbl, fmt)

    def _set_slider(self, key: str, value: float) -> None:
        if key in self.sliders:
            var, val_lbl, fmt = self.sliders[key]
            var.set(value)
            val_lbl.configure(text=fmt.format(value))

    def _populate_from_data(self, data: Dict[str, Any]) -> None:
        sw = data.get("swarm", {})
        self._set_slider("num_agents", sw.get("num_agents", 50))
        self._set_slider("max_speed", sw.get("max_speed", 3.2))

        rad = data.get("flocking_radii", {})
        self._set_slider("perception_radius", rad.get("perception_radius", 68.0))
        self._set_slider("separation_radius", rad.get("separation_radius", 28.0))

        w = data.get("weights", {})
        self._set_slider("separation", w.get("separation", 2.10))
        self._set_slider("alignment", w.get("alignment", 1.05))
        self._set_slider("cohesion", w.get("cohesion", 0.85))
        self._set_slider("obstacle_avoidance", w.get("obstacle_avoidance", 3.40))
        self._set_slider("wander", w.get("wander", 0.20))

        dtn = data.get("dtn_network", {})
        self._set_slider("comm_radius", dtn.get("comm_radius", 80.0))
        self._set_slider("bandwidth_rate", dtn.get("bandwidth_rate", 0.035))
        self.los_var.set(bool(dtn.get("require_line_of_sight", True)))

    def _on_preset_selected(self, _: Any = None) -> None:
        preset_name = self.preset_var.get()
        preset = SCENARIO_PRESETS.get(preset_name, {})
        self.preset_desc_lbl.configure(text=preset.get("description", ""))
        self._populate_from_data(preset)

    def save_config(self) -> bool:
        try:
            self.current_data.setdefault("swarm", {})
            self.current_data["swarm"]["num_agents"] = int(
                self.sliders["num_agents"][0].get()
            )
            self.current_data["swarm"]["max_speed"] = round(
                float(self.sliders["max_speed"][0].get()), 2
            )

            self.current_data.setdefault("flocking_radii", {})
            self.current_data["flocking_radii"]["perception_radius"] = round(
                float(self.sliders["perception_radius"][0].get()), 1
            )
            self.current_data["flocking_radii"]["separation_radius"] = round(
                float(self.sliders["separation_radius"][0].get()), 1
            )

            self.current_data.setdefault("weights", {})
            for k in (
                "separation",
                "alignment",
                "cohesion",
                "obstacle_avoidance",
                "wander",
            ):
                self.current_data["weights"][k] = round(
                    float(self.sliders[k][0].get()), 2
                )

            self.current_data.setdefault("dtn_network", {})
            self.current_data["dtn_network"]["comm_radius"] = round(
                float(self.sliders["comm_radius"][0].get()), 1
            )
            self.current_data["dtn_network"]["bandwidth_rate"] = round(
                float(self.sliders["bandwidth_rate"][0].get()), 4
            )
            self.current_data["dtn_network"]["require_line_of_sight"] = bool(
                self.los_var.get()
            )

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.current_data, f, indent=4)
            return True
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save config.json:\n{exc}")
            return False

    def save_and_launch(self) -> None:
        if self.save_config():
            subprocess.Popen(
                [sys.executable, str(MAIN_SCRIPT)], cwd=str(MAIN_SCRIPT.parent)
            )


if __name__ == "__main__":
    tk_root = tk.Tk()
    app = ConfiguratorApp(tk_root)
    tk_root.mainloop()
