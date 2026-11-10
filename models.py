"""
Structures de données et entités (Obstacles, Paquets, Ondes) — Rendu sobre.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from config import CONFIG


class NodeState(Enum):
    """État épidémiologique / DTN d'un agent autonome."""
    HEALTHY = auto()    # Bleu : Aucune donnée stockée
    SYNCING = auto()    # En cours de téléchargement
    INFECTED = auto()   # Rouge : Données complètes téléchargées


@dataclass
class Obstacle:
    """Obstacle physique circulaire solide (rendu simple)."""
    position: pygame.math.Vector2
    radius: float

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface, show_debug: bool = False) -> None:
        center = (int(self.position.x), int(self.position.y))
        r = int(self.radius)

        if show_debug:
            safety_r = int(self.radius + CONFIG.OBSTACLE_DETECTION_MARGIN)
            pygame.draw.circle(surface, (180, 180, 180), center, safety_r, 1)

        # Cercle plein gris avec contour foncé simple
        pygame.draw.circle(surface, CONFIG.COLOR_OBSTACLE_FILL, center, r)
        pygame.draw.circle(surface, CONFIG.COLOR_OBSTACLE_RING, center, r, 2)


@dataclass
class DataPacketVisual:
    """Petit point circulant sur un lien lors d'un transfert de données."""
    source_id: int
    target_id: int
    progress: float = 0.0
    speed: float = 0.08


@dataclass
class RippleWave:
    """Cercle simple indiquant la fin d'un téléchargement."""
    position: pygame.math.Vector2
    radius: float = 8.0
    max_radius: float = 40.0

    def update(self) -> bool:
        self.radius += 1.8
        return self.radius < self.max_radius

    def draw(self, surface: pygame.Surface) -> None:
        center = (int(self.position.x), int(self.position.y))
        pygame.draw.circle(surface, CONFIG.COLOR_RED_NODE, center, int(self.radius), 1)
