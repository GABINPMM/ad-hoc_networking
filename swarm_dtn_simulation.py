"""
Simulation Multi-Agents : Robotique en Essaim (Boids) & Réseau DTN
==================================================================
Version Monobloc (Un seul fichier complet pour annexe de rapport académique)
Style graphique sobre et minimaliste (fond clair, gris, bleu et rouge).

Contrôles :
-----------
- [ESPACE]          : Pause / Reprendre la simulation
- [R]               : Réinitialiser la simulation (nouveau Patient Zéro)
- [G]               : Afficher / Masquer la grille spatiale et les rayons radio
- [V]               : Afficher / Masquer les vecteurs de vitesse et d'évitement
- [Clic Gauche]     : Infecter l'agent le plus proche
- [MAJ+Clic Gauche] : Ajouter un obstacle solide sous le curseur
- [Clic Droit]      : Supprimer un obstacle sous le curseur
"""

from __future__ import annotations

import math
import random
import sys
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

import pygame


# ============================================================================
# 1. CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class SimConfig:
    SCREEN_WIDTH: int = 1360
    SCREEN_HEIGHT: int = 820
    HUD_WIDTH: int = 320
    WORLD_WIDTH: int = 1040
    WORLD_HEIGHT: int = 820
    FPS: int = 60
    WINDOW_TITLE: str = "Simulation Multi-Agents (Boids & DTN)"

    NUM_AGENTS: int = 50
    AGENT_RADIUS: float = 6.0

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

    GRID_CELL_SIZE: int = 80

    # Palette sobre (fond clair, gris, bleu et rouge uniquement)
    BG_COLOR: Tuple[int, int, int] = (242, 242, 242)
    GRID_LINE_COLOR: Tuple[int, int, int] = (222, 222, 222)
    HUD_BG_COLOR: Tuple[int, int, int] = (228, 228, 228)
    HUD_BORDER_COLOR: Tuple[int, int, int] = (120, 120, 120)

    COLOR_BLUE_NODE: Tuple[int, int, int] = (30, 100, 210)
    COLOR_RED_NODE: Tuple[int, int, int] = (210, 40, 40)

    COLOR_OBSTACLE_FILL: Tuple[int, int, int] = (175, 175, 175)
    COLOR_OBSTACLE_RING: Tuple[int, int, int] = (70, 70, 70)
    COLOR_TEXT_PRIMARY: Tuple[int, int, int] = (20, 20, 20)
    COLOR_TEXT_MUTED: Tuple[int, int, int] = (80, 80, 80)


CONFIG = SimConfig()


# ============================================================================
# 2. STRUCTURES DE DONNÉES
# ============================================================================

class NodeState(Enum):
    HEALTHY = auto()
    SYNCING = auto()
    INFECTED = auto()


@dataclass
class Obstacle:
    position: pygame.math.Vector2
    radius: float

    def draw(self, surface: pygame.Surface, show_debug: bool = False) -> None:
        center = (int(self.position.x), int(self.position.y))
        r = int(self.radius)
        if show_debug:
            safety_r = int(self.radius + CONFIG.OBSTACLE_DETECTION_MARGIN)
            pygame.draw.circle(surface, (180, 180, 180), center, safety_r, 1)

        pygame.draw.circle(surface, CONFIG.COLOR_OBSTACLE_FILL, center, r)
        pygame.draw.circle(surface, CONFIG.COLOR_OBSTACLE_RING, center, r, 2)


@dataclass
class DataPacketVisual:
    source_id: int
    target_id: int
    progress: float = 0.0
    speed: float = 0.08


@dataclass
class RippleWave:
    position: pygame.math.Vector2
    radius: float = 8.0
    max_radius: float = 40.0

    def update(self) -> bool:
        self.radius += 1.8
        return self.radius < self.max_radius

    def draw(self, surface: pygame.Surface) -> None:
        center = (int(self.position.x), int(self.position.y))
        pygame.draw.circle(
            surface, CONFIG.COLOR_RED_NODE, center, int(self.radius), 1
        )


# ============================================================================
# 3. GRILLE DE HACHAGE SPATIAL (O(N))
# ============================================================================

class SpatialHashGrid:
    def __init__(self, cell_size: int) -> None:
        self.cell_size: int = cell_size
        self.cells: Dict[Tuple[int, int], List[SwarmAgent]] = {}

    def clear(self) -> None:
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


# ============================================================================
# 4. AGENT AUTONOME (BOIDS + DTN)
# ============================================================================

class SwarmAgent:
    def __init__(
        self,
        agent_id: int,
        position: pygame.math.Vector2,
        is_patient_zero: bool = False,
    ) -> None:
        self.id: int = agent_id
        self.position: pygame.math.Vector2 = pygame.math.Vector2(position)

        angle = random.uniform(0.0, math.tau)
        speed = random.uniform(CONFIG.MIN_SPEED, CONFIG.MAX_SPEED)
        self.velocity: pygame.math.Vector2 = pygame.math.Vector2(
            math.cos(angle) * speed, math.sin(angle) * speed
        )
        self.acceleration: pygame.math.Vector2 = pygame.math.Vector2(0.0, 0.0)
        self.wander_angle: float = angle

        self.state: NodeState = (
            NodeState.INFECTED if is_patient_zero else NodeState.HEALTHY
        )
        self.payload_progress: float = 1.0 if is_patient_zero else 0.0
        self.is_patient_zero: bool = is_patient_zero
        self.active_peers: Set[int] = set()
        self.packets_forwarded: int = 0
        self.infection_timestamp: Optional[float] = 0.0 if is_patient_zero else None

        self.last_obstacle_force: pygame.math.Vector2 = pygame.math.Vector2(0, 0)

    @staticmethod
    def _limit_vector(
        vec: pygame.math.Vector2, max_magnitude: float
    ) -> pygame.math.Vector2:
        sq_len = vec.length_squared()
        if sq_len > max_magnitude * max_magnitude and sq_len > 1e-9:
            return vec.normalize() * max_magnitude
        return vec

    def _steer_towards(self, desired: pygame.math.Vector2) -> pygame.math.Vector2:
        if desired.length_squared() < 1e-9:
            return pygame.math.Vector2(0.0, 0.0)
        desired_scaled = desired.normalize() * CONFIG.MAX_SPEED
        steer = desired_scaled - self.velocity
        return self._limit_vector(steer, CONFIG.MAX_FORCE)

    def compute_flocking(
        self, neighbors: List[SwarmAgent]
    ) -> Tuple[pygame.math.Vector2, pygame.math.Vector2, pygame.math.Vector2]:
        sep_accum = pygame.math.Vector2(0.0, 0.0)
        ali_accum = pygame.math.Vector2(0.0, 0.0)
        coh_accum = pygame.math.Vector2(0.0, 0.0)

        sep_count = 0
        flock_count = 0
        sep_rad_sq = CONFIG.SEPARATION_RADIUS ** 2

        for other in neighbors:
            if other.id == self.id:
                continue

            offset = self.position - other.position
            dist_sq = offset.length_squared()
            if dist_sq < 1e-6:
                continue

            ali_accum += other.velocity
            coh_accum += other.position
            flock_count += 1

            if dist_sq < sep_rad_sq:
                dist = math.sqrt(dist_sq)
                sep_accum += (offset / dist) * (
                    CONFIG.SEPARATION_RADIUS / max(dist, 1.0)
                )
                sep_count += 1

        sep_force = pygame.math.Vector2(0.0, 0.0)
        ali_force = pygame.math.Vector2(0.0, 0.0)
        coh_force = pygame.math.Vector2(0.0, 0.0)

        if sep_count > 0:
            sep_force = self._steer_towards(sep_accum / sep_count)

        if flock_count > 0:
            ali_force = self._steer_towards(ali_accum / flock_count)
            center_of_mass = coh_accum / flock_count
            coh_force = self._steer_towards(center_of_mass - self.position)

        return sep_force, ali_force, coh_force

    def compute_obstacle_avoidance(
        self, obstacles: List[Obstacle]
    ) -> pygame.math.Vector2:
        avoid_force = pygame.math.Vector2(0.0, 0.0)
        heading = (
            self.velocity.normalize()
            if self.velocity.length_squared() > 1e-6
            else pygame.math.Vector2(1.0, 0.0)
        )

        look_ahead = CONFIG.OBSTACLE_DETECTION_MARGIN * (
            0.6 + 0.4 * (self.velocity.length() / CONFIG.MAX_SPEED)
        )

        for obs in obstacles:
            to_agent = self.position - obs.position
            dist = to_agent.length()
            safe_radius = (
                obs.radius + CONFIG.AGENT_RADIUS + CONFIG.OBSTACLE_DETECTION_MARGIN
            )

            if dist < safe_radius and dist > 1e-5:
                normal = to_agent / dist
                penetration = (safe_radius - dist) / CONFIG.OBSTACLE_DETECTION_MARGIN
                penetration = max(0.0, min(1.5, penetration))

                radial_push = normal * (penetration ** 2) * 2.4

                tangent = pygame.math.Vector2(-normal.y, normal.x)
                if tangent.dot(heading) < 0:
                    tangent = -tangent
                tangential_push = tangent * penetration * 1.35

                avoid_force += radial_push + tangential_push

            proj = (obs.position - self.position).dot(heading)
            if 0.0 < proj < look_ahead + obs.radius:
                closest_pt = self.position + heading * proj
                perp_vec = closest_pt - obs.position
                perp_dist = perp_vec.length()
                clearance = obs.radius + CONFIG.AGENT_RADIUS + 14.0
                if perp_dist < clearance:
                    if perp_dist > 1e-4:
                        lat_dir = perp_vec / perp_dist
                    else:
                        lat_dir = pygame.math.Vector2(-heading.y, heading.x)
                    urgency = (clearance - perp_dist) / clearance
                    avoid_force += lat_dir * urgency * 1.8

        self.last_obstacle_force = self._limit_vector(
            avoid_force, CONFIG.MAX_FORCE * 2.5
        )
        return self.last_obstacle_force

    def compute_boundary_containment(self) -> pygame.math.Vector2:
        desired = pygame.math.Vector2(0.0, 0.0)
        m = CONFIG.WALL_MARGIN
        w = CONFIG.WORLD_WIDTH
        h = CONFIG.WORLD_HEIGHT

        if self.position.x < m:
            desired.x = CONFIG.MAX_SPEED * ((m - self.position.x) / m)
        elif self.position.x > w - m:
            desired.x = -CONFIG.MAX_SPEED * ((self.position.x - (w - m)) / m)

        if self.position.y < m:
            desired.y = CONFIG.MAX_SPEED * ((m - self.position.y) / m)
        elif self.position.y > h - m:
            desired.y = -CONFIG.MAX_SPEED * ((self.position.y - (h - m)) / m)

        if desired.length_squared() > 1e-6:
            steer = desired - self.velocity
            return self._limit_vector(steer, CONFIG.MAX_FORCE * 1.6)
        return pygame.math.Vector2(0.0, 0.0)

    def compute_wander(self) -> pygame.math.Vector2:
        self.wander_angle += random.uniform(-0.35, 0.35)
        circle_center = (
            self.velocity.normalize() * 25.0
            if self.velocity.length_squared() > 1e-6
            else pygame.math.Vector2(25.0, 0.0)
        )
        displacement = pygame.math.Vector2(
            math.cos(self.wander_angle) * 12.0,
            math.sin(self.wander_angle) * 12.0,
        )
        wander_force = circle_center + displacement
        return self._limit_vector(wander_force, CONFIG.MAX_FORCE * 0.5)

    def update_kinematics(
        self,
        neighbors: List[SwarmAgent],
        obstacles: List[Obstacle],
    ) -> None:
        sep, ali, coh = self.compute_flocking(neighbors)
        obs = self.compute_obstacle_avoidance(obstacles)
        bnd = self.compute_boundary_containment()
        wnd = self.compute_wander()

        self.acceleration = (
            sep * CONFIG.WEIGHT_SEPARATION
            + ali * CONFIG.WEIGHT_ALIGNMENT
            + coh * CONFIG.WEIGHT_COHESION
            + obs * CONFIG.WEIGHT_OBSTACLE
            + bnd * CONFIG.WEIGHT_BOUNDARY
            + wnd * CONFIG.WEIGHT_WANDER
        )

        self.velocity += self.acceleration
        speed = self.velocity.length()
        if speed > CONFIG.MAX_SPEED:
            self.velocity.scale_to_length(CONFIG.MAX_SPEED)
        elif 1e-5 < speed < CONFIG.MIN_SPEED:
            self.velocity.scale_to_length(CONFIG.MIN_SPEED)

        self.position += self.velocity

        for obstacle in obstacles:
            diff = self.position - obstacle.position
            dist = diff.length()
            min_dist = obstacle.radius + CONFIG.AGENT_RADIUS + 2.0
            if dist < min_dist:
                normal = (
                    diff / dist
                    if dist > 1e-5
                    else pygame.math.Vector2(1.0, 0.0)
                )
                self.position = obstacle.position + normal * min_dist
                vn = self.velocity.dot(normal)
                if vn < 0:
                    self.velocity -= (1.5 * vn) * normal

        pad = CONFIG.AGENT_RADIUS + 3.0
        if self.position.x < pad:
            self.position.x = pad
            self.velocity.x = abs(self.velocity.x)
        elif self.position.x > CONFIG.WORLD_WIDTH - pad:
            self.position.x = CONFIG.WORLD_WIDTH - pad
            self.velocity.x = -abs(self.velocity.x)

        if self.position.y < pad:
            self.position.y = pad
            self.velocity.y = abs(self.velocity.y)
        elif self.position.y > CONFIG.WORLD_HEIGHT - pad:
            self.position.y = CONFIG.WORLD_HEIGHT - pad
            self.velocity.y = -abs(self.velocity.y)

    def get_primary_color(self) -> Tuple[int, int, int]:
        if self.state == NodeState.INFECTED:
            return CONFIG.COLOR_RED_NODE
        if self.state == NodeState.SYNCING:
            t = max(0.0, min(1.0, self.payload_progress))
            r = int(
                CONFIG.COLOR_BLUE_NODE[0] * (1 - t) + CONFIG.COLOR_RED_NODE[0] * t
            )
            g = int(
                CONFIG.COLOR_BLUE_NODE[1] * (1 - t) + CONFIG.COLOR_RED_NODE[1] * t
            )
            b = int(
                CONFIG.COLOR_BLUE_NODE[2] * (1 - t) + CONFIG.COLOR_RED_NODE[2] * t
            )
            return (r, g, b)
        return CONFIG.COLOR_BLUE_NODE

    def draw(
        self,
        surface: pygame.Surface,
        show_comm_radius: bool = False,
        show_vectors: bool = False,
    ) -> None:
        cx, cy = int(self.position.x), int(self.position.y)
        color = self.get_primary_color()

        if show_comm_radius:
            pygame.draw.circle(
                surface, (180, 180, 180), (cx, cy), int(CONFIG.COMM_RADIUS), 1
            )

        heading_angle = math.atan2(self.velocity.y, self.velocity.x)
        r = CONFIG.AGENT_RADIUS * 1.4

        nose = (
            int(self.position.x + math.cos(heading_angle) * r * 1.4),
            int(self.position.y + math.sin(heading_angle) * r * 1.4),
        )
        left_wing = (
            int(self.position.x + math.cos(heading_angle + 2.4) * r),
            int(self.position.y + math.sin(heading_angle + 2.4) * r),
        )
        right_wing = (
            int(self.position.x + math.cos(heading_angle - 2.4) * r),
            int(self.position.y + math.sin(heading_angle - 2.4) * r),
        )

        pts = [nose, left_wing, right_wing]
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (30, 30, 30), pts, 1)

        if self.is_patient_zero:
            pygame.draw.circle(
                surface, (30, 30, 30), (cx, cy), int(CONFIG.AGENT_RADIUS * 2.0), 1
            )

        if 0.0 < self.payload_progress < 1.0:
            rect = pygame.Rect(cx - 10, cy - 10, 20, 20)
            pygame.draw.arc(
                surface,
                CONFIG.COLOR_RED_NODE,
                rect,
                0.0,
                self.payload_progress * math.tau,
                2,
            )

        if show_vectors:
            vel_end = self.position + self.velocity * 6.5
            pygame.draw.line(
                surface,
                (50, 50, 50),
                (cx, cy),
                (int(vel_end.x), int(vel_end.y)),
                1,
            )
            if self.last_obstacle_force.length_squared() > 1e-4:
                obs_end = self.position + self.last_obstacle_force * 120.0
                pygame.draw.line(
                    surface,
                    CONFIG.COLOR_RED_NODE,
                    (cx, cy),
                    (int(obs_end.x), int(obs_end.y)),
                    1,
                )


# ============================================================================
# 5. CONTRÔLEUR DTN (RÉSEAU AD-HOC)
# ============================================================================

class DTNController:
    def __init__(self) -> None:
        self.active_links: List[Tuple[SwarmAgent, SwarmAgent, bool]] = []
        self.packets: List[DataPacketVisual] = []
        self.ripples: List[RippleWave] = []
        self.total_transmissions_completed: int = 1
        self.frame_counter: int = 0

    @staticmethod
    def _line_of_sight_clear(
        p1: pygame.math.Vector2,
        p2: pygame.math.Vector2,
        obstacles: List[Obstacle],
    ) -> bool:
        seg = p2 - p1
        seg_len_sq = seg.length_squared()
        if seg_len_sq < 1e-6:
            return True

        for obs in obstacles:
            t = max(0.0, min(1.0, (obs.position - p1).dot(seg) / seg_len_sq))
            closest = p1 + seg * t
            if (closest - obs.position).length_squared() < (obs.radius * 0.85) ** 2:
                return False
        return True

    def step(
        self,
        agents: List[SwarmAgent],
        spatial_grid: SpatialHashGrid,
        obstacles: List[Obstacle],
        sim_time: float,
    ) -> None:
        self.frame_counter += 1
        self.active_links.clear()
        agent_map: Dict[int, SwarmAgent] = {a.id: a for a in agents}

        for agent in agents:
            agent.active_peers.clear()

        visited_pairs: Set[Tuple[int, int]] = set()

        for agent in agents:
            neighbors = spatial_grid.query_radius(
                agent.position, CONFIG.COMM_RADIUS
            )
            for peer in neighbors:
                if peer.id == agent.id:
                    continue

                pair_key = (
                    (agent.id, peer.id)
                    if agent.id < peer.id
                    else (peer.id, agent.id)
                )
                if pair_key in visited_pairs:
                    continue
                visited_pairs.add(pair_key)

                if not self._line_of_sight_clear(
                    agent.position, peer.position, obstacles
                ):
                    continue

                agent.active_peers.add(peer.id)
                peer.active_peers.add(agent.id)

                is_transferring = False
                transmitter: Optional[SwarmAgent] = None
                receiver: Optional[SwarmAgent] = None

                if (
                    agent.state == NodeState.INFECTED
                    and peer.state != NodeState.INFECTED
                ):
                    transmitter, receiver = agent, peer
                elif (
                    peer.state == NodeState.INFECTED
                    and agent.state != NodeState.INFECTED
                ):
                    transmitter, receiver = peer, agent

                if transmitter is not None and receiver is not None:
                    is_transferring = True
                    receiver.state = NodeState.SYNCING
                    dist = (transmitter.position - receiver.position).length()
                    snr_boost = 1.0 + 0.6 * (
                        1.0 - min(1.0, dist / CONFIG.COMM_RADIUS)
                    )
                    receiver.payload_progress += CONFIG.BANDWIDTH_RATE * snr_boost

                    if self.frame_counter % CONFIG.PACKET_SPAWN_INTERVAL == 0:
                        self.packets.append(
                            DataPacketVisual(
                                source_id=transmitter.id,
                                target_id=receiver.id,
                            )
                        )

                    if receiver.payload_progress >= 1.0:
                        receiver.payload_progress = 1.0
                        receiver.state = NodeState.INFECTED
                        receiver.infection_timestamp = sim_time
                        transmitter.packets_forwarded += 1
                        self.total_transmissions_completed += 1
                        self.ripples.append(
                            RippleWave(pygame.math.Vector2(receiver.position))
                        )

                self.active_links.append((agent, peer, is_transferring))

        surviving_packets: List[DataPacketVisual] = []
        for pkt in self.packets:
            pkt.progress += pkt.speed
            if (
                pkt.progress < 1.0
                and pkt.source_id in agent_map
                and pkt.target_id in agent_map
            ):
                surviving_packets.append(pkt)
        self.packets = surviving_packets

        self.ripples = [r for r in self.ripples if r.update()]

    def draw(
        self, surface: pygame.Surface, agent_map: Dict[int, SwarmAgent]
    ) -> None:
        for node_a, node_b, is_transferring in self.active_links:
            p1 = (int(node_a.position.x), int(node_a.position.y))
            p2 = (int(node_b.position.x), int(node_b.position.y))

            if is_transferring:
                pygame.draw.line(surface, CONFIG.COLOR_RED_NODE, p1, p2, 2)
            else:
                pygame.draw.line(surface, (190, 190, 190), p1, p2, 1)

        for pkt in self.packets:
            src = agent_map[pkt.source_id]
            dst = agent_map[pkt.target_id]
            pos = src.position.lerp(dst.position, pkt.progress)
            pygame.draw.circle(
                surface, (30, 30, 30), (int(pos.x), int(pos.y)), 3
            )

        for ripple in self.ripples:
            ripple.draw(surface)


# ============================================================================
# 6. TABLEAU DE BORD SOBRE (HUD)
# ============================================================================

class DashboardHUD:
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

    def reset(self) -> None:
        self.history.clear()
        self.sample_timer = 0
        self.convergence_time = None

    def update_metrics(
        self,
        agents: List[SwarmAgent],
        sim_time: float,
    ) -> Dict[str, float]:
        total = len(agents)
        infected = sum(1 for a in agents if a.state == NodeState.INFECTED)
        syncing = sum(1 for a in agents if a.state == NodeState.SYNCING)
        healthy = total - infected - syncing
        connected = sum(1 for a in agents if len(a.active_peers) > 0)
        total_degrees = sum(len(a.active_peers) for a in agents)

        prop_pct = (infected / total) * 100.0 if total > 0 else 0.0
        conn_pct = (connected / total) * 100.0 if total > 0 else 0.0
        avg_degree = total_degrees / total if total > 0 else 0.0

        if infected == total and self.convergence_time is None:
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
        sub_surf = self.font_small.render(
            "Simulation Boids & Reseau Ad-Hoc", True, CONFIG.COLOR_TEXT_MUTED
        )
        surface.blit(sub_surf, (x0 + pad, y))
        y += 18

        box1 = pygame.Rect(x0 + pad, y, cw, 148)
        self._draw_box(surface, box1, "1. PROPAGATION DES DONNEES")

        prop_pct = metrics["prop_pct"]
        pct_surf = self.font_metric.render(
            f"{prop_pct:5.1f}%", True, CONFIG.COLOR_RED_NODE
        )
        surface.blit(pct_surf, (box1.right - pct_surf.get_width() - 10, box1.y + 4))

        bar_rect = pygame.Rect(box1.x + 10, box1.y + 34, cw - 20, 12)
        pygame.draw.rect(surface, (215, 215, 215), bar_rect)

        inf_w = int((cw - 20) * (metrics["infected"] / metrics["total"]))
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

        box4 = pygame.Rect(x0 + pad, y, cw, CONFIG.SCREEN_HEIGHT - y - 12)
        self._draw_box(surface, box4, "4. PARAMETRES & COMMANDES")

        info_rows = [
            f"Temps : {sim_time:5.1f}s | FPS : {fps:4.0f} ({'PAUSE' if paused else 'ACTIF'})",
            f"Boids S/A/C : {CONFIG.WEIGHT_SEPARATION:.1f} / {CONFIG.WEIGHT_ALIGNMENT:.1f} / {CONFIG.WEIGHT_COHESION:.1f}",
            "----------------------------------",
            "[ESPACE] : Pause / Reprendre",
            "[R]      : Reinitialiser",
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
            ry += 17


# ============================================================================
# 7. MOTEUR PRINCIPAL DE LA SIMULATION
# ============================================================================

class SimulationEngine:
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
            Obstacle(pygame.math.Vector2(280, 220), 50.0),
            Obstacle(pygame.math.Vector2(740, 210), 55.0),
            Obstacle(pygame.math.Vector2(510, 410), 65.0),
            Obstacle(pygame.math.Vector2(270, 610), 52.0),
            Obstacle(pygame.math.Vector2(760, 600), 48.0),
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

        self.dtn.ripples.append(
            RippleWave(pygame.math.Vector2(self.agents[0].position))
        )

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
                    self._initialize_world()
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
                            Obstacle(click_pos, random.uniform(42.0, 62.0))
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

        self.spatial_grid.clear()
        for agent in self.agents:
            self.spatial_grid.insert(agent)

        for agent in self.agents:
            local_neighbors = self.spatial_grid.query_radius(
                agent.position, CONFIG.PERCEPTION_RADIUS
            )
            agent.update_kinematics(local_neighbors, self.obstacles)

        self.spatial_grid.clear()
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

    def _render(self) -> None:
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

        metrics = self.hud.update_metrics(self.agents, self.sim_time)
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
            self._render()

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    engine = SimulationEngine()
    engine.run()
