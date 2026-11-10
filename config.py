# Configuration module
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


CONFIG_FILE_PATH = Path(__file__).parent / "config.json"


@dataclass
class SimConfig:
    SCREEN_WIDTH: int = 1360
    SCREEN_HEIGHT: int = 820
    HUD_WIDTH: int = 320
    WORLD_WIDTH: int = 1040
    WORLD_HEIGHT: int = 820
    FPS: int = 60
    WINDOW_TITLE: str = "Multi-Agent Simulation (Boids & DTN)"

    NUM_AGENTS: int = 50
    AGENT_RADIUS: float = 6.0
    TRAIL_LENGTH: int = 0

    MAX_SPEED: float = 3.2
    MIN_SPEED: float = 1.6
    MAX_FORCE: float = 0.14

    PERCEPTION_RADIUS: float = 68.0
    SEPARATION_RADIUS: float = 28.0
    OBSTACLE_DETECTION_MARGIN: float = 50.0
    WALL_MARGIN: float = 55.0

    WEIGHT_SEPARATION: float = 2.10
    WEIGHT_ALIGNMENT: float = 1.05
    WEIGHT_COHESION: float = 0.85
    WEIGHT_OBSTACLE: float = 3.40
    WEIGHT_BOUNDARY: float = 2.50
    WEIGHT_WANDER: float = 0.20

    COMM_RADIUS: float = 80.0
    BANDWIDTH_RATE: float = 0.035
    PACKET_SPAWN_INTERVAL: int = 5
    REQUIRE_LINE_OF_SIGHT: bool = True

    GRID_CELL_SIZE: int = 80

    BG_COLOR: Tuple[int, int, int] = (242, 242, 242)
    GRID_LINE_COLOR: Tuple[int, int, int] = (222, 222, 222)
    HUD_BG_COLOR: Tuple[int, int, int] = (228, 228, 228)
    HUD_BORDER_COLOR: Tuple[int, int, int] = (120, 120, 120)

    COLOR_BLUE_NODE: Tuple[int, int, int] = (30, 100, 210)
    COLOR_SYNC_NODE: Tuple[int, int, int] = (210, 40, 40)
    COLOR_RED_NODE: Tuple[int, int, int] = (210, 40, 40)

    COLOR_OBSTACLE_FILL: Tuple[int, int, int] = (175, 175, 175)
    COLOR_OBSTACLE_RING: Tuple[int, int, int] = (70, 70, 70)
    COLOR_TEXT_PRIMARY: Tuple[int, int, int] = (20, 20, 20)
    COLOR_TEXT_MUTED: Tuple[int, int, int] = (80, 80, 80)
    COLOR_ACCENT: Tuple[int, int, int] = (20, 20, 20)

    INITIAL_OBSTACLES: List[Dict[str, float]] = field(
        default_factory=lambda: [
            {"x": 280.0, "y": 220.0, "radius": 50.0},
            {"x": 740.0, "y": 210.0, "radius": 55.0},
            {"x": 510.0, "y": 410.0, "radius": 65.0},
            {"x": 270.0, "y": 610.0, "radius": 52.0},
            {"x": 760.0, "y": 600.0, "radius": 48.0},
        ]
    )

    def reload(self, json_path: Path = CONFIG_FILE_PATH) -> bool:
        if not json_path.exists():
            return False
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

            win = data.get("window", {})
            self.SCREEN_WIDTH = int(win.get("screen_width", self.SCREEN_WIDTH))
            self.SCREEN_HEIGHT = int(win.get("screen_height", self.SCREEN_HEIGHT))
            self.HUD_WIDTH = int(win.get("hud_width", self.HUD_WIDTH))
            self.WORLD_WIDTH = self.SCREEN_WIDTH - self.HUD_WIDTH
            self.WORLD_HEIGHT = self.SCREEN_HEIGHT
            self.FPS = int(win.get("fps", self.FPS))
            self.WINDOW_TITLE = str(win.get("title", self.WINDOW_TITLE))

            sw = data.get("swarm", {})
            self.NUM_AGENTS = int(sw.get("num_agents", self.NUM_AGENTS))
            self.AGENT_RADIUS = float(sw.get("agent_radius", self.AGENT_RADIUS))
            self.TRAIL_LENGTH = int(sw.get("trail_length", self.TRAIL_LENGTH))
            self.MAX_SPEED = float(sw.get("max_speed", self.MAX_SPEED))
            self.MIN_SPEED = float(sw.get("min_speed", self.MIN_SPEED))
            self.MAX_FORCE = float(sw.get("max_force", self.MAX_FORCE))

            rad = data.get("flocking_radii", {})
            self.PERCEPTION_RADIUS = float(
                rad.get("perception_radius", self.PERCEPTION_RADIUS)
            )
            self.SEPARATION_RADIUS = float(
                rad.get("separation_radius", self.SEPARATION_RADIUS)
            )
            self.OBSTACLE_DETECTION_MARGIN = float(
                rad.get("obstacle_detection_margin", self.OBSTACLE_DETECTION_MARGIN)
            )
            self.WALL_MARGIN = float(rad.get("wall_margin", self.WALL_MARGIN))

            w = data.get("weights", {})
            self.WEIGHT_SEPARATION = float(w.get("separation", self.WEIGHT_SEPARATION))
            self.WEIGHT_ALIGNMENT = float(w.get("alignment", self.WEIGHT_ALIGNMENT))
            self.WEIGHT_COHESION = float(w.get("cohesion", self.WEIGHT_COHESION))
            self.WEIGHT_OBSTACLE = float(
                w.get("obstacle_avoidance", self.WEIGHT_OBSTACLE)
            )
            self.WEIGHT_BOUNDARY = float(w.get("boundary", self.WEIGHT_BOUNDARY))
            self.WEIGHT_WANDER = float(w.get("wander", self.WEIGHT_WANDER))

            dtn = data.get("dtn_network", {})
            self.COMM_RADIUS = float(dtn.get("comm_radius", self.COMM_RADIUS))
            self.BANDWIDTH_RATE = float(dtn.get("bandwidth_rate", self.BANDWIDTH_RATE))
            self.PACKET_SPAWN_INTERVAL = max(
                1, int(dtn.get("packet_spawn_interval", self.PACKET_SPAWN_INTERVAL))
            )
            self.REQUIRE_LINE_OF_SIGHT = bool(
                dtn.get("require_line_of_sight", self.REQUIRE_LINE_OF_SIGHT)
            )

            self.GRID_CELL_SIZE = max(
                32, int(max(self.PERCEPTION_RADIUS, self.COMM_RADIUS))
            )

            col = data.get("colors", {})
            if "background" in col:
                self.BG_COLOR = tuple(col["background"])
            if "grid_line" in col:
                self.GRID_LINE_COLOR = tuple(col["grid_line"])
            if "hud_background" in col:
                self.HUD_BG_COLOR = tuple(col["hud_background"])
            if "hud_border" in col:
                self.HUD_BORDER_COLOR = tuple(col["hud_border"])
            if "blue_node" in col:
                self.COLOR_BLUE_NODE = tuple(col["blue_node"])
            if "sync_node" in col:
                self.COLOR_SYNC_NODE = tuple(col["sync_node"])
            if "red_node" in col:
                self.COLOR_RED_NODE = tuple(col["red_node"])
            if "obstacle_fill" in col:
                self.COLOR_OBSTACLE_FILL = tuple(col["obstacle_fill"])
            if "obstacle_ring" in col:
                self.COLOR_OBSTACLE_RING = tuple(col["obstacle_ring"])
            if "accent" in col:
                self.COLOR_ACCENT = tuple(col["accent"])

            if "initial_obstacles" in data:
                self.INITIAL_OBSTACLES = data["initial_obstacles"]

            return True
        except Exception:
            return False


CONFIG = SimConfig()
CONFIG.reload()
