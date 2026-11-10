"""
Tableau de bord analytique sobre (HUD) affichant les métriques temps réel,
le pourcentage de propagation, le nombre d'agents connectés et la courbe S.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple

import pygame

from agent import SwarmAgent
from config import CONFIG
from dtn import DTNController
from models import NodeState


class DashboardHUD:
    """Panneau latéral sobre et lisible pour rapport académique."""

    def __init__(self) -> None:
        pygame.font.init()
        self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_header = pygame.font.SysFont("consolas", 13, bold=True)
        self.font_body = pygame.font.SysFont("consolas", 12)
        self.font_metric = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 11)

        self.history: deque[Tuple[float, float]] = deque(maxlen=240)
        self.sample_timer: int = 0
        self.convergence_time: Optional[float] = None
        self.status_banner_text: str = ""
        self.status_banner_timer: float = 0.0

    def reset(self) -> None:
        self.history.clear()
        self.sample_timer = 0
        self.convergence_time = None

    def notify(self, message: str, duration: float = 2.5) -> None:
        self.status_banner_text = message
        self.status_banner_timer = duration

    def update_metrics(
        self,
        agents: List[SwarmAgent],
        sim_time: float,
        dt: float = 0.016,
    ) -> Dict[str, float]:
        if self.status_banner_timer > 0.0:
            self.status_banner_timer = max(0.0, self.status_banner_timer - dt)

        total = len(agents)
        infected = sum(1 for a in agents if a.state == NodeState.INFECTED)
        syncing = sum(1 for a in agents if a.state == NodeState.SYNCING)
        healthy = total - infected - syncing
        connected = sum(1 for a in agents if len(a.active_peers) > 0)
        total_degrees = sum(len(a.active_peers) for a in agents)

        prop_pct = (infected / total) * 100.0 if total > 0 else 0.0
        conn_pct = (connected / total) * 100.0 if total > 0 else 0.0
        avg_degree = total_degrees / total if total > 0 else 0.0

        if infected == total and total > 0 and self.convergence_time is None:
            self.convergence_time = sim_time

        self.sample_timer += 1
        if self.sample_timer % 3 == 0:
            self.history.append((prop_pct, conn_pct))

        return {
            "total": float(total),
            "infected": float(infected),
            "syncing": float(syncing),
            "healthy": float(healthy),
            "connected": float(connected),
            "prop_pct": prop_pct,
            "conn_pct": conn_pct,
            "avg_degree": avg_degree,
        }

    def _draw_box(
        self, surface: pygame.Surface, rect: pygame.Rect, title: str
    ) -> None:
        pygame.draw.rect(surface, (245, 245, 245), rect)
        pygame.draw.rect(surface, CONFIG.HUD_BORDER_COLOR, rect, 1)
        lbl = self.font_header.render(title, True, CONFIG.COLOR_TEXT_PRIMARY)
        surface.blit(lbl, (rect.x + 10, rect.y + 7))
        pygame.draw.line(
            surface,
            (190, 190, 190),
            (rect.x, rect.y + 26),
            (rect.right, rect.y + 26),
            1,
        )

    def draw(
        self,
        surface: pygame.Surface,
        metrics: Dict[str, float],
        dtn: DTNController,
        sim_time: float,
        fps: float,
        paused: bool,
        show_grid: bool,
        show_vectors: bool,
    ) -> None:
        x0 = CONFIG.WORLD_WIDTH
        panel_rect = pygame.Rect(x0, 0, CONFIG.HUD_WIDTH, CONFIG.SCREEN_HEIGHT)
        pygame.draw.rect(surface, CONFIG.HUD_BG_COLOR, panel_rect)
        pygame.draw.line(
            surface,
            CONFIG.HUD_BORDER_COLOR,
            (x0, 0),
            (x0, CONFIG.SCREEN_HEIGHT),
            2,
        )

        pad = 12
        cw = CONFIG.HUD_WIDTH - 2 * pad
        y = 12

        title_surf = self.font_title.render(
            "TABLEAU DE BORD (DTN)", True, CONFIG.COLOR_TEXT_PRIMARY
        )
        surface.blit(title_surf, (x0 + pad, y))
        y += 20

        if self.status_banner_timer > 0.0:
            sub_surf = self.font_small.render(
                self.status_banner_text, True, CONFIG.COLOR_RED_NODE
            )
        else:
            sub_surf = self.font_small.render(
                "Simulation Boids & Reseau Ad-Hoc",
                True,
                CONFIG.COLOR_TEXT_MUTED,
            )
        surface.blit(sub_surf, (x0 + pad, y))
        y += 18

        # --------------------------------------------------------------------
        # BLOC 1 : PROPAGATION DES DONNÉES
        # --------------------------------------------------------------------
        box1 = pygame.Rect(x0 + pad, y, cw, 148)
        self._draw_box(surface, box1, "1. PROPAGATION DES DONNEES")

        prop_pct = metrics["prop_pct"]
        pct_surf = self.font_metric.render(
            f"{prop_pct:5.1f}%", True, CONFIG.COLOR_RED_NODE
        )
        surface.blit(pct_surf, (box1.right - pct_surf.get_width() - 10, box1.y + 4))

        bar_rect = pygame.Rect(box1.x + 10, box1.y + 34, cw - 20, 12)
        pygame.draw.rect(surface, (215, 215, 215), bar_rect)

        total_safe = max(1.0, metrics["total"])
        inf_w = int((cw - 20) * (metrics["infected"] / total_safe))
        if inf_w > 0:
            pygame.draw.rect(
                surface,
                CONFIG.COLOR_RED_NODE,
                pygame.Rect(bar_rect.x, bar_rect.y, inf_w, bar_rect.height),
            )
        pygame.draw.rect(surface, CONFIG.HUD_BORDER_COLOR, bar_rect, 1)

        rows = [
            (
                "Agents porteurs (Rouge) :",
                f"{int(metrics['infected']):02d}/{int(metrics['total']):02d}",
                CONFIG.COLOR_RED_NODE,
            ),
            (
                "En telechargement       :",
                f"{int(metrics['syncing']):02d}/{int(metrics['total']):02d}",
                CONFIG.COLOR_TEXT_PRIMARY,
            ),
            (
                "Agents sains (Bleu)     :",
                f"{int(metrics['healthy']):02d}/{int(metrics['total']):02d}",
                CONFIG.COLOR_BLUE_NODE,
            ),
            (
                "Temps de convergence    :",
                f"{self.convergence_time:.1f} s"
                if self.convergence_time is not None
                else "En cours",
                CONFIG.COLOR_TEXT_PRIMARY,
            ),
        ]
        ry = box1.y + 54
        for label, val, col in rows:
            l_surf = self.font_body.render(label, True, CONFIG.COLOR_TEXT_MUTED)
            v_surf = self.font_body.render(val, True, col)
            surface.blit(l_surf, (box1.x + 10, ry))
            surface.blit(v_surf, (box1.right - v_surf.get_width() - 10, ry))
            ry += 21

        y += box1.height + 10

        # --------------------------------------------------------------------
        # BLOC 2 : CONNECTIVITÉ RÉSEAU
        # --------------------------------------------------------------------
        box2 = pygame.Rect(x0 + pad, y, cw, 122)
        self._draw_box(surface, box2, "2. CONNECTIVITE RESEAU")

        topo_rows = [
            (
                "Agents connectes        :",
                f"{int(metrics['connected']):02d}/{int(metrics['total']):02d} ({metrics['conn_pct']:.0f}%)",
            ),
            ("Liens P2P actifs        :", f"{len(dtn.active_links):d}"),
            ("Voisins moyens <k>      :", f"{metrics['avg_degree']:.2f}"),
            ("Portee radio (rayon)    :", f"{CONFIG.COMM_RADIUS:.0f} px"),
        ]
        ry = box2.y + 34
        for label, val in topo_rows:
            l_surf = self.font_body.render(label, True, CONFIG.COLOR_TEXT_MUTED)
            v_surf = self.font_body.render(val, True, CONFIG.COLOR_TEXT_PRIMARY)
            surface.blit(l_surf, (box2.x + 10, ry))
            surface.blit(v_surf, (box2.right - v_surf.get_width() - 10, ry))
            ry += 20

        y += box2.height + 10

        # --------------------------------------------------------------------
        # BLOC 3 : COURBE D'ÉVOLUTION TEMPS RÉEL
        # --------------------------------------------------------------------
        box3 = pygame.Rect(x0 + pad, y, cw, 175)
        self._draw_box(surface, box3, "3. COURBE DE PROPAGATION")

        plot_rect = pygame.Rect(box3.x + 34, box3.y + 34, cw - 44, 110)
        pygame.draw.rect(surface, (255, 255, 255), plot_rect)
        pygame.draw.rect(surface, CONFIG.HUD_BORDER_COLOR, plot_rect, 1)

        for frac in (0.0, 0.5, 1.0):
            gy = int(plot_rect.bottom - frac * plot_rect.height)
            pygame.draw.line(
                surface, (225, 225, 225), (plot_rect.left, gy), (plot_rect.right, gy), 1
            )
            axis_lbl = self.font_small.render(
                f"{int(frac * 100)}%", True, CONFIG.COLOR_TEXT_MUTED
            )
            surface.blit(axis_lbl, (box3.x + 4, gy - 6))

        if len(self.history) >= 2:
            n_pts = len(self.history)
            prop_pts: List[Tuple[int, int]] = []
            conn_pts: List[Tuple[int, int]] = []

            for i, (p_val, c_val) in enumerate(self.history):
                px = int(
                    plot_rect.left + (i / max(1, n_pts - 1)) * (plot_rect.width - 2)
                )
                py_prop = int(
                    plot_rect.bottom - (p_val / 100.0) * (plot_rect.height - 2)
                )
                py_conn = int(
                    plot_rect.bottom - (c_val / 100.0) * (plot_rect.height - 2)
                )
                prop_pts.append((px, py_prop))
                conn_pts.append((px, py_conn))

            pygame.draw.lines(surface, CONFIG.COLOR_BLUE_NODE, False, conn_pts, 1)
            pygame.draw.lines(surface, CONFIG.COLOR_RED_NODE, False, prop_pts, 2)

        leg_y = plot_rect.bottom + 6
        pygame.draw.line(
            surface,
            CONFIG.COLOR_RED_NODE,
            (box3.x + 12, leg_y + 6),
            (box3.x + 26, leg_y + 6),
            2,
        )
        surface.blit(
            self.font_small.render("Propagation %", True, CONFIG.COLOR_TEXT_PRIMARY),
            (box3.x + 32, leg_y),
        )
        pygame.draw.line(
            surface,
            CONFIG.COLOR_BLUE_NODE,
            (box3.x + 145, leg_y + 6),
            (box3.x + 159, leg_y + 6),
            1,
        )
        surface.blit(
            self.font_small.render("Connectes %", True, CONFIG.COLOR_TEXT_PRIMARY),
            (box3.x + 165, leg_y),
        )

        y += box3.height + 10

        # --------------------------------------------------------------------
        # BLOC 4 : PARAMÈTRES & COMMANDES
        # --------------------------------------------------------------------
        box4 = pygame.Rect(x0 + pad, y, cw, CONFIG.SCREEN_HEIGHT - y - 12)
        self._draw_box(surface, box4, "4. PARAMETRES & COMMANDES")

        info_rows = [
            f"Temps : {sim_time:5.1f}s | FPS : {fps:4.0f} ({'PAUSE' if paused else 'ACTIF'})",
            f"Boids S/A/C : {CONFIG.WEIGHT_SEPARATION:.1f} / {CONFIG.WEIGHT_ALIGNMENT:.1f} / {CONFIG.WEIGHT_COHESION:.1f}",
            "----------------------------------",
            "[ESPACE] : Pause / Reprendre",
            "[R]      : Reinitialiser",
            "[C]      : Recharger config.json",
            "[S]/[E]  : Capture PNG / Export CSV",
            f"[G] ({'ON' if show_grid else 'OFF'}) : Grille & Rayons Radio",
            f"[V] ({'ON' if show_vectors else 'OFF'}) : Vecteurs de Vitesse",
            "[Clic G] : Infecter un agent",
            "[MAJ+G]  : Ajouter un obstacle",
            "[Clic D] : Supprimer un obstacle",
        ]
        ry = box4.y + 32
        for line_str in info_rows:
            surf_line = self.font_small.render(
                line_str, True, CONFIG.COLOR_TEXT_PRIMARY
            )
            surface.blit(surf_line, (box4.x + 10, ry))
            ry += 16
