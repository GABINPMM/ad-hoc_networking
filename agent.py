# Autonomous swarm agent implementation
from __future__ import annotations

import math
import random
from collections import deque
from typing import List, Optional, Set, Tuple

import pygame

from config import CONFIG
from models import NodeState, Obstacle


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

        self.trail: deque[pygame.math.Vector2] = deque(maxlen=max(0, CONFIG.TRAIL_LENGTH))

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
            0.6 + 0.4 * (self.velocity.length() / max(0.1, CONFIG.MAX_SPEED))
        )

        for obs in obstacles:
            to_agent = self.position - obs.position
            dist = to_agent.length()
            safe_radius = (
                obs.radius + CONFIG.AGENT_RADIUS + CONFIG.OBSTACLE_DETECTION_MARGIN
            )

            if dist < safe_radius and dist > 1e-5:
                normal = to_agent / dist
                penetration = (safe_radius - dist) / max(
                    1.0, CONFIG.OBSTACLE_DETECTION_MARGIN
                )
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
        m = max(10.0, CONFIG.WALL_MARGIN)
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

        if CONFIG.TRAIL_LENGTH > 0:
            if self.trail.maxlen != CONFIG.TRAIL_LENGTH:
                self.trail = deque(self.trail, maxlen=CONFIG.TRAIL_LENGTH)
            self.trail.append(pygame.math.Vector2(self.position))

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
            self.velocity.y = abs(self.velocity.x) if self.velocity.y == 0 else abs(self.velocity.y)
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
