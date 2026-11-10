"""
Grille de hachage spatial uniforme 2D (Complexité O(N) pour le voisinage).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Tuple

import pygame

if TYPE_CHECKING:
    from agent import SwarmAgent


class SpatialHashGrid:
    """
    Partitionne l'espace 2D en cellules uniformes afin d'accélérer
    les requêtes de voisinage (Boids et découverte réseau DTN).
    """

    def __init__(self, cell_size: int) -> None:
        self.cell_size: int = max(16, cell_size)
        self.cells: Dict[Tuple[int, int], List[SwarmAgent]] = {}

    def clear(self, new_cell_size: int | None = None) -> None:
        if new_cell_size is not None:
            self.cell_size = max(16, new_cell_size)
        self.cells.clear()

    def _hash(self, position: pygame.math.Vector2) -> Tuple[int, int]:
        return (
            int(position.x // self.cell_size),
            int(position.y // self.cell_size),
        )

    def insert(self, agent: SwarmAgent) -> None:
        cell_coords = self._hash(agent.position)
        if cell_coords not in self.cells:
            self.cells[cell_coords] = []
        self.cells[cell_coords].append(agent)

    def query_radius(
        self, position: pygame.math.Vector2, radius: float
    ) -> List[SwarmAgent]:
        """Retourne tous les agents situés à une distance <= radius."""
        cx, cy = self._hash(position)
        cell_span = int(math.ceil(radius / self.cell_size))
        radius_sq = radius * radius
        neighbors: List[SwarmAgent] = []

        for dx in range(-cell_span, cell_span + 1):
            for dy in range(-cell_span, cell_span + 1):
                bucket = self.cells.get((cx + dx, cy + dy))
                if not bucket:
                    continue
                for candidate in bucket:
                    if (candidate.position - position).length_squared() <= radius_sq:
                        neighbors.append(candidate)
        return neighbors

