"""
Point d'entrée principal de la simulation modulaire.
Exécutez ce fichier via `lancer_simulation.bat` ou `python main.py`.
"""

from __future__ import annotations

import csv
import random
import sys
import time
from pathlib import Path
from typing import List

import pygame

from agent import SwarmAgent
from config import CONFIG
from dtn import DTNController
from hud import DashboardHUD
from models import NodeState, Obstacle, RippleWave
from spatial_grid import SpatialHashGrid


class SimulationEngine:
    """
    Orchestrateur principal gérant le cycle de vie de la simulation,
    les obstacles solides, l'essaim de 50 agents et le routage DTN.
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(CONFIG.WINDOW_TITLE)
        self.screen = pygame.display.set_mode(
            (CONFIG.SCREEN_WIDTH, CONFIG.SCREEN_HEIGHT),
            pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        self.clock = pygame.time.Clock()

        self.spatial_grid = SpatialHashGrid(CONFIG.GRID_CELL_SIZE)
        self.dtn = DTNController()
        self.hud = DashboardHUD()

        self.obstacles: List[Obstacle] = []
        self.agents: List[SwarmAgent] = []

        self.sim_time: float = 0.0
        self.paused: bool = False
        self.show_grid_and_radii: bool = False
        self.show_vectors: bool = False

        self._initialize_world()

    def _initialize_obstacles(self) -> None:
        self.obstacles = [
            Obstacle(
                pygame.math.Vector2(float(obs["x"]), float(obs["y"])),
                float(obs["radius"]),
            )
            for obs in CONFIG.INITIAL_OBSTACLES
        ]

    def _find_valid_spawn(self) -> pygame.math.Vector2:
        margin = CONFIG.WALL_MARGIN + 15.0
        for _ in range(500):
            candidate = pygame.math.Vector2(
                random.uniform(margin, CONFIG.WORLD_WIDTH - margin),
                random.uniform(margin, CONFIG.WORLD_HEIGHT - margin),
            )
            collision = any(
                (candidate - obs.position).length()
                < obs.radius + CONFIG.AGENT_RADIUS + 25.0
                for obs in self.obstacles
            )
            if not collision:
                return candidate
        return pygame.math.Vector2(100.0, 100.0)

    def _initialize_world(self) -> None:
        self.sim_time = 0.0
        self.dtn = DTNController()
        self.hud.reset()
        self._initialize_obstacles()

        self.agents.clear()
        for idx in range(CONFIG.NUM_AGENTS):
            spawn_pos = self._find_valid_spawn()
            agent = SwarmAgent(
                agent_id=idx,
                position=spawn_pos,
                is_patient_zero=(idx == 0),
            )
            self.agents.append(agent)

        if self.agents:
            self.dtn.ripples.append(
                RippleWave(pygame.math.Vector2(self.agents[0].position))
            )

    def _hot_reload_config(self) -> None:
        """Recharge config.json en direct sans fermer la fenêtre."""
        old_num_agents = len(self.agents)
        if CONFIG.reload():
            pygame.display.set_caption(CONFIG.WINDOW_TITLE)
            # Ajuster le nombre d'agents si modifié dans config.json
            if CONFIG.NUM_AGENTS > old_num_agents:
                for idx in range(old_num_agents, CONFIG.NUM_AGENTS):
                    self.agents.append(
                        SwarmAgent(
                            agent_id=idx,
                            position=self._find_valid_spawn(),
                            is_patient_zero=False,
                        )
                    )
            elif CONFIG.NUM_AGENTS < old_num_agents:
                self.agents = self.agents[: max(1, CONFIG.NUM_AGENTS)]
            self.hud.notify("config.json rechargé avec succès !")
        else:
            self.hud.notify("Erreur lors du rechargement de config.json")

    def _save_screenshot(self) -> None:
        """Sauvegarde une capture d'écran HD dans le dossier captures/."""
        out_dir = Path(__file__).parent / "captures"
        out_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = out_dir / f"capture_essaim_{stamp}.png"
        pygame.image.save(self.screen, str(filepath))
        self.hud.notify(f"Capture enregistrée : captures/{filepath.name}")

    def _export_csv(self) -> None:
        """Exporte l'historique de propagation et de connectivité en CSV."""
        out_dir = Path(__file__).parent / "captures"
        out_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = out_dir / f"telemetrie_dtn_{stamp}.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["echantillon", "propagation_pct", "connectivite_pct"])
            for idx, (prop_pct, conn_pct) in enumerate(self.hud.history):
                writer.writerow([idx, f"{prop_pct:.2f}", f"{conn_pct:.2f}"])
        self.hud.notify(f"CSV exporté : captures/{filepath.name}")

    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    CONFIG.reload()
                    self._initialize_world()
                    self.hud.notify("Simulation réinitialisée (Patient Zéro)")
                elif event.key == pygame.K_c:
                    self._hot_reload_config()
                elif event.key == pygame.K_s:
                    self._save_screenshot()
                elif event.key == pygame.K_e:
                    self._export_csv()
                elif event.key == pygame.K_g:
                    self.show_grid_and_radii = not self.show_grid_and_radii
                elif event.key == pygame.K_v:
                    self.show_vectors = not self.show_vectors

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if mx < CONFIG.WORLD_WIDTH:
                    click_pos = pygame.math.Vector2(mx, my)
                    mods = pygame.key.get_mods()

                    if event.button == 1 and (mods & pygame.KMOD_SHIFT):
                        self.obstacles.append(
                            Obstacle(click_pos, random.uniform(42.0, 64.0))
                        )
                    elif event.button == 1 and self.agents:
                        nearest = min(
                            self.agents,
                            key=lambda a: (a.position - click_pos).length_squared(),
                        )
                        if (nearest.position - click_pos).length() < 80.0:
                            nearest.state = NodeState.INFECTED
                            nearest.payload_progress = 1.0
                            self.dtn.ripples.append(
                                RippleWave(pygame.math.Vector2(nearest.position))
                            )
                    elif event.button == 3:
                        self.obstacles = [
                            obs
                            for obs in self.obstacles
                            if (obs.position - click_pos).length() > obs.radius
                        ]
        return True

    def _update(self, dt: float) -> None:
        if self.paused:
            return

        self.sim_time += dt

        self.spatial_grid.clear(CONFIG.GRID_CELL_SIZE)
        for agent in self.agents:
            self.spatial_grid.insert(agent)

        for obs in self.obstacles:
            obs.update(dt)

        for agent in self.agents:
            local_neighbors = self.spatial_grid.query_radius(
                agent.position, CONFIG.PERCEPTION_RADIUS
            )
            agent.update_kinematics(local_neighbors, self.obstacles)

        self.spatial_grid.clear(CONFIG.GRID_CELL_SIZE)
        for agent in self.agents:
            self.spatial_grid.insert(agent)

        self.dtn.step(
            self.agents, self.spatial_grid, self.obstacles, self.sim_time
        )

    def _draw_world_background(self) -> None:
        self.screen.fill(CONFIG.BG_COLOR)

        if self.show_grid_and_radii:
            step = CONFIG.GRID_CELL_SIZE
            for x in range(0, CONFIG.WORLD_WIDTH, step):
                pygame.draw.line(
                    self.screen,
                    CONFIG.GRID_LINE_COLOR,
                    (x, 0),
                    (x, CONFIG.WORLD_HEIGHT),
                    1,
                )
            for y in range(0, CONFIG.WORLD_HEIGHT, step):
                pygame.draw.line(
                    self.screen,
                    CONFIG.GRID_LINE_COLOR,
                    (0, y),
                    (CONFIG.WORLD_WIDTH, y),
                    1,
                )

        arena_rect = pygame.Rect(0, 0, CONFIG.WORLD_WIDTH, CONFIG.WORLD_HEIGHT)
        pygame.draw.rect(self.screen, CONFIG.HUD_BORDER_COLOR, arena_rect, 1)

    def _render(self, dt: float) -> None:
        self._draw_world_background()

        for obs in self.obstacles:
            obs.draw(self.screen, show_debug=self.show_grid_and_radii)

        agent_map = {a.id: a for a in self.agents}
        self.dtn.draw(self.screen, agent_map)

        for agent in self.agents:
            agent.draw(
                self.screen,
                show_comm_radius=self.show_grid_and_radii,
                show_vectors=self.show_vectors,
            )

        metrics = self.hud.update_metrics(self.agents, self.sim_time, dt)
        self.hud.draw(
            surface=self.screen,
            metrics=metrics,
            dtn=self.dtn,
            sim_time=self.sim_time,
            fps=self.clock.get_fps(),
            paused=self.paused,
            show_grid=self.show_grid_and_radii,
            show_vectors=self.show_vectors,
        )

        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(CONFIG.FPS) / 1000.0
            running = self._handle_events()
            self._update(dt)
            self._render(dt)

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    engine = SimulationEngine()
    engine.run()

