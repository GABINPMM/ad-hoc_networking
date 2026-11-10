"""
Automatic Benchmark & Figure Generator for the Academic Report.
Runs 4 distinct simulation scenarios until 100% data propagation (consensus)
and saves screenshots, a comparative plot, and a CSV table in `captures/`.
"""

from __future__ import annotations

import csv
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from config import CONFIG
from main import SimulationEngine
from models import NodeState


CAPTURES_DIR = Path(__file__).parent / "captures"


def generate_timeline_screenshots() -> None:
    """Generates 3 screenshots (Start, Mid-propagation, 100% Consensus)."""
    print("[1/2] Generating timeline screenshots...")
    CONFIG.reload()
    random.seed(42)
    engine = SimulationEngine()

    dt = 1.0 / 60.0
    saved_start = False
    saved_mid = False
    saved_end = False

    for step in range(2400):  # Up to 40 simulated seconds
        engine._update(dt)
        infected_count = sum(
            1 for a in engine.agents if a.state == NodeState.INFECTED
        )
        prop_ratio = infected_count / max(1, len(engine.agents))

        if step == 20 and not saved_start:
            engine._render(dt)
            pygame.image.save(
                engine.screen, str(CAPTURES_DIR / "1_etat_initial.png")
            )
            saved_start = True

        if prop_ratio >= 0.45 and not saved_mid:
            engine._render(dt)
            pygame.image.save(
                engine.screen, str(CAPTURES_DIR / "2_propagation_en_cours.png")
            )
            saved_mid = True

        if prop_ratio >= 1.0 and not saved_end:
            for _ in range(15):
                engine._update(dt)
                engine._render(dt)
            pygame.image.save(
                engine.screen, str(CAPTURES_DIR / "3_consensus_final.png")
            )
            saved_end = True
            print(f"  -> 100% Consensus reached at t = {engine.sim_time:.2f} s")
            break


def run_scenario_benchmark() -> None:
    """Emulates 4 scenarios until 100% consensus and saves plot + CSV."""
    print("[2/2] Emulating 4 scenarios...")

    scenarios: List[Dict[str, Any]] = [
        {
            "name": "Scenario 1: Balanced Swarm (Default, R=80px)",
            "color": (210, 40, 40),
            "params": {
                "WEIGHT_SEPARATION": 2.10,
                "WEIGHT_ALIGNMENT": 1.05,
                "WEIGHT_COHESION": 0.85,
                "WEIGHT_WANDER": 0.20,
                "COMM_RADIUS": 80.0,
                "BANDWIDTH_RATE": 0.035,
            },
        },
        {
            "name": "Scenario 2: High-Cohesion Flocking (R=80px)",
            "color": (30, 100, 210),
            "params": {
                "WEIGHT_SEPARATION": 1.65,
                "WEIGHT_ALIGNMENT": 1.90,
                "WEIGHT_COHESION": 1.75,
                "WEIGHT_WANDER": 0.15,
                "COMM_RADIUS": 80.0,
                "BANDWIDTH_RATE": 0.035,
            },
        },
        {
            "name": "Scenario 3: Dispersed Exploration (Random Gas, R=80px)",
            "color": (40, 150, 60),
            "params": {
                "WEIGHT_SEPARATION": 3.20,
                "WEIGHT_ALIGNMENT": 0.15,
                "WEIGHT_COHESION": 0.10,
                "WEIGHT_WANDER": 0.80,
                "COMM_RADIUS": 80.0,
                "BANDWIDTH_RATE": 0.035,
            },
        },
        {
            "name": "Scenario 4: Short-Range DTN (R=52px, Store-Carry-Forward)",
            "color": (140, 70, 180),
            "params": {
                "WEIGHT_SEPARATION": 2.10,
                "WEIGHT_ALIGNMENT": 1.05,
                "WEIGHT_COHESION": 0.85,
                "WEIGHT_WANDER": 0.35,
                "COMM_RADIUS": 52.0,
                "BANDWIDTH_RATE": 0.035,
            },
        },
    ]

    max_seconds = 32.0
    dt = 1.0 / 60.0
    total_steps = int(max_seconds / dt)

    results_curves: Dict[str, List[Tuple[float, float]]] = {}
    summary_rows: List[List[str]] = []

    for sc in scenarios:
        CONFIG.reload()
        for k, v in sc["params"].items():
            setattr(CONFIG, k, v)

        random.seed(7)
        engine = SimulationEngine()

        curve: List[Tuple[float, float]] = []
        t_25: float | None = None
        t_50: float | None = None
        t_100: float | None = None
        degree_accum = 0.0
        total_links_accum = 0.0

        for step in range(total_steps):
            engine._update(dt)
            t = (step + 1) * dt
            total = len(engine.agents)
            infected = sum(
                1 for a in engine.agents if a.state == NodeState.INFECTED
            )
            pct = (infected / total) * 100.0
            avg_k = sum(len(a.active_peers) for a in engine.agents) / total
            conn_pct = (
                sum(1 for a in engine.agents if len(a.active_peers) > 0) / total
            ) * 100.0
            degree_accum += avg_k
            total_links_accum += conn_pct

            if pct >= 25.0 and t_25 is None:
                t_25 = t
            if pct >= 50.0 and t_50 is None:
                t_50 = t
            if pct >= 100.0 and t_100 is None:
                t_100 = t

            if step % 4 == 0:
                curve.append((t, pct))

        results_curves[sc["name"]] = curve
        mean_k = degree_accum / total_steps
        mean_conn = total_links_accum / total_steps
        final_pct = curve[-1][1] if curve else 0.0

        summary_rows.append(
            [
                sc["name"],
                f"{t_25:.2f} s" if t_25 else f">{max_seconds:.0f}s",
                f"{t_50:.2f} s" if t_50 else f">{max_seconds:.0f}s",
                f"{t_100:.2f} s" if t_100 else f">{max_seconds:.0f}s",
                f"{mean_k:.2f}",
                f"{mean_conn:.1f}%",
                f"{final_pct:.1f}%",
            ]
        )
        print(
            f"  -> {sc['name']} | T_25%={summary_rows[-1][1]} | T_50%={summary_rows[-1][2]} | T_100%={summary_rows[-1][3]} | <k>={mean_k:.2f} | Conn={mean_conn:.1f}% | Final={final_pct:.1f}%"
        )

    csv_path = CAPTURES_DIR / "tableau_resultats_rapport.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Scenario",
                "Time to 25%",
                "Time to 50%",
                "Time to 100% (Consensus)",
                "Average Node Degree <k>",
                "Mean Connected Agents %",
                "Final Propagation %",
            ]
        )
        writer.writerows(summary_rows)

    fig_w, fig_h = 980, 600
    surf = pygame.Surface((fig_w, fig_h))
    surf.fill((255, 255, 255))

    font_title = pygame.font.SysFont("consolas", 17, bold=True)
    font_axis = pygame.font.SysFont("consolas", 13, bold=True)
    font_tick = pygame.font.SysFont("consolas", 12)
    font_leg = pygame.font.SysFont("consolas", 11)

    title_s = font_title.render(
        "DTN Data Propagation Convergence Across Swarm Scenarios (N = 50 Agents)",
        True,
        (20, 20, 20),
    )
    surf.blit(title_s, (75, 22))

    plot_rect = pygame.Rect(75, 65, 850, 380)
    pygame.draw.rect(surf, (250, 250, 250), plot_rect)
    pygame.draw.rect(surf, (80, 80, 80), plot_rect, 1)

    for pct_tick in (0, 20, 40, 60, 80, 100):
        y = int(plot_rect.bottom - (pct_tick / 100.0) * plot_rect.height)
        pygame.draw.line(
            surf, (225, 225, 225), (plot_rect.left, y), (plot_rect.right, y), 1
        )
        lbl = font_tick.render(f"{pct_tick:3d}%", True, (60, 60, 60))
        surf.blit(lbl, (plot_rect.left - 42, y - 7))

    for sec_tick in range(0, int(max_seconds) + 1, 4):
        x = int(plot_rect.left + (sec_tick / max_seconds) * plot_rect.width)
        pygame.draw.line(
            surf, (225, 225, 225), (x, plot_rect.top), (x, plot_rect.bottom), 1
        )
        lbl = font_tick.render(f"{sec_tick}s", True, (60, 60, 60))
        surf.blit(lbl, (x - 8, plot_rect.bottom + 8))

    x_title = font_axis.render("Simulation Time (seconds)", True, (30, 30, 30))
    surf.blit(
        x_title,
        (plot_rect.centerx - x_title.get_width() // 2, plot_rect.bottom + 30),
    )

    for sc in scenarios:
        pts: List[Tuple[int, int]] = []
        for t, pct in results_curves[sc["name"]]:
            px = int(plot_rect.left + (t / max_seconds) * plot_rect.width)
            py = int(plot_rect.bottom - (pct / 100.0) * plot_rect.height)
            pts.append((px, py))
        if len(pts) >= 2:
            pygame.draw.lines(surf, sc["color"], False, pts, 2)

    leg_box = pygame.Rect(75, 485, 850, 88)
    pygame.draw.rect(surf, (245, 245, 245), leg_box)
    pygame.draw.rect(surf, (160, 160, 160), leg_box, 1)

    for idx, sc in enumerate(scenarios):
        col_x = leg_box.x + 14 + (idx % 2) * 420
        row_y = leg_box.y + 16 + (idx // 2) * 34
        pygame.draw.line(
            surf, sc["color"], (col_x, row_y + 7), (col_x + 24, row_y + 7), 3
        )
        txt = f"{sc['name']} [100% at {summary_rows[idx][3]}]"
        surf.blit(font_leg.render(txt, True, (25, 25, 25)), (col_x + 30, row_y))

    fig_path = CAPTURES_DIR / "comparaison_scenarios_rapport.png"
    pygame.image.save(surf, str(fig_path))


if __name__ == "__main__":
    CAPTURES_DIR.mkdir(exist_ok=True)
    generate_timeline_screenshots()
    run_scenario_benchmark()
    CONFIG.reload()
    print("[DONE]")
