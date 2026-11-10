"""
Contrôleur du réseau tolérant aux délais et perturbations (DTN / MANET).
Rendu sobre des connexions et des paquets transférés.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import pygame

from agent import SwarmAgent
from config import CONFIG
from models import DataPacketVisual, NodeState, Obstacle, RippleWave
from spatial_grid import SpatialHashGrid


class DTNController:
    """
    Implémente le protocole Store-Carry-Forward :
    lorsqu'un agent sain (Bleu) entre dans le rayon de communication d'un
    agent porteur (Rouge), il télécharge progressivement la charge utile
    et devient à son tour un relais actif.
    """

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
        if not CONFIG.REQUIRE_LINE_OF_SIGHT:
            return True

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
                        1.0 - min(1.0, dist / max(1.0, CONFIG.COMM_RADIUS))
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
        # Lignes de connexion simples
        for node_a, node_b, is_transferring in self.active_links:
            p1 = (int(node_a.position.x), int(node_a.position.y))
            p2 = (int(node_b.position.x), int(node_b.position.y))

            if is_transferring:
                pygame.draw.line(surface, CONFIG.COLOR_RED_NODE, p1, p2, 2)
            else:
                pygame.draw.line(surface, (190, 190, 190), p1, p2, 1)

        # Petits points pour les paquets en cours de transfert
        for pkt in self.packets:
            src = agent_map[pkt.source_id]
            dst = agent_map[pkt.target_id]
            pos = src.position.lerp(dst.position, pkt.progress)
            pygame.draw.circle(
                surface, (30, 30, 30), (int(pos.x), int(pos.y)), 3
            )

        for ripple in self.ripples:
            ripple.draw(surface)
