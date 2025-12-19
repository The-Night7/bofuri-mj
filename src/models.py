from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Literal
import time
import uuid


# ----------------------------
# Runtime combat entities
# ----------------------------

@dataclass
class RuntimeEntity:
  name: str
  kind: str  # "PJ" | "Mob" | "Boss"
  level: int

  hp_max: float
  mp_max: float

  STR: float
  AGI: float
  INT: float
  DEX: float
  VIT: float

  hp: float
  mp: float

  # Infos bestiaire / MJ
  base_attack: Optional[float] = None
  zone: Optional[str] = None
  drops: Optional[List[str]] = None
  abilities: Optional[List[str]] = None
  extra: Optional[Dict[str, Any]] = None  # poison/tour etc.

  def reset(self) -> None:
    self.hp = float(self.hp_max)
    self.mp = float(self.mp_max)


# ----------------------------
# Persistent players
# ----------------------------

@dataclass
class Player:
  name: str
  level: int

  hp_max: float
  mp_max: float

  STR: float
  AGI: float
  INT: float
  DEX: float
  VIT: float

  hp: Optional[float] = None
  mp: Optional[float] = None

  def ensure_current(self) -> None:
    if self.hp is None:
      self.hp = float(self.hp_max)
    if self.mp is None:
      self.mp = float(self.mp_max)

  def reset(self) -> None:
    self.hp = float(self.hp_max)
    self.mp = float(self.mp_max)

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "Player":
    p = Player(
      name=d["name"],
      level=int(d.get("level", 1)),
      hp_max=float(d.get("hp_max", 0)),
      mp_max=float(d.get("mp_max", 0)),
      STR=float(d.get("STR", 0)),
      AGI=float(d.get("AGI", 0)),
      INT=float(d.get("INT", 0)),
      DEX=float(d.get("DEX", 0)),
      VIT=float(d.get("VIT", 0)),
      hp=float(d["hp"]) if "hp" in d else None,
      mp=float(d["mp"]) if "mp" in d else None,
    )
    p.ensure_current()
    return p

  def to_dict(self) -> Dict[str, Any]:
    self.ensure_current()
    return asdict(self)


# ----------------------------
# Compendium (bestiaire + skills)
# ----------------------------

@dataclass
class MonsterVariant:
  level: int
  hp_max: float
  mp_max: float
  STR: float
  AGI: float
  INT: float
  DEX: float
  VIT: float
  base_attack: Optional[float] = None
  extra: Optional[Dict[str, Any]] = None


@dataclass
class Monster:
  name: str
  palier: Optional[str] = None         # "Palier 1" etc.
  level_range: Optional[str] = None    # ex: "1-10"
  rarity: Optional[str] = None
  zone: Optional[str] = None
  drops: Optional[List[str]] = None
  abilities: Optional[List[str]] = None
  variants: Dict[int, MonsterVariant] = None


@dataclass
class Skill:
  name: str
  category: Optional[str] = None
  description: Optional[str] = None
  cost_mp: Optional[str] = None
  condition: Optional[str] = None
  palier: Optional[str] = None


@dataclass
class Compendium:
  monsters: Dict[str, Monster]
  skills: Dict[str, Skill]

  def to_dict(self) -> Dict[str, Any]:
    def monster_variant_to_dict(v: MonsterVariant) -> Dict[str, Any]:
      return asdict(v)

    def monster_to_dict(m: Monster) -> Dict[str, Any]:
      d = asdict(m)
      d["variants"] = {str(k): monster_variant_to_dict(v) for k, v in (m.variants or {}).items()}
      return d

    return {
      "monsters": {k: monster_to_dict(v) for k, v in self.monsters.items()},
      "skills": {k: asdict(v) for k, v in self.skills.items()},
    }

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "Compendium":
    monsters: Dict[str, Monster] = {}
    for name, md in d.get("monsters", {}).items():
      variants: Dict[int, MonsterVariant] = {}
      for lk, vd in (md.get("variants", {}) or {}).items():
        variants[int(lk)] = MonsterVariant(
          level=int(vd["level"]),
          hp_max=float(vd["hp_max"]),
          mp_max=float(vd["mp_max"]),
          STR=float(vd["STR"]),
          AGI=float(vd["AGI"]),
          INT=float(vd["INT"]),
          DEX=float(vd["DEX"]),
          VIT=float(vd["VIT"]),
          base_attack=float(vd["base_attack"]) if vd.get("base_attack") is not None else None,
          extra=vd.get("extra"),
        )

      monsters[name] = Monster(
        name=md.get("name", name),
        palier=md.get("palier"),
        level_range=md.get("level_range"),
        rarity=md.get("rarity"),
        zone=md.get("zone"),
        drops=md.get("drops"),
        abilities=md.get("abilities"),
        variants=variants,
      )

    skills: Dict[str, Skill] = {}
    for name, sd in d.get("skills", {}).items():
      skills[name] = Skill(**sd)

    return Compendium(monsters=monsters, skills=skills)


# ----------------------------
# Encounter (multi-combat)
# ----------------------------

Side = Literal["player", "mob"]


@dataclass
class Participant:
  id: str
  side: Side
  runtime: RuntimeEntity


@dataclass
class ActionLogEntry:
  ts: float
  round: int
  turn_index: int
  actor_id: str
  actor_name: str
  target_id: Optional[str]
  target_name: Optional[str]
  action_type: str  # "basic_attack" | "skill"
  skill_name: Optional[str]
  roll_a: float
  roll_b: float
  perce_armure: bool
  vit_div: float
  result: Dict[str, Any]

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


@dataclass
class EncounterState:
  encounter_id: str = field(default_factory=lambda: str(uuid.uuid4()))
  created_ts: float = field(default_factory=lambda: time.time())

  participants: List[Participant] = field(default_factory=list)

  # turn management
  turn_index: int = 0  # increments each action
  round: int = 1       # computed from turn_index and number of active participants

  log: List[ActionLogEntry] = field(default_factory=list)

  def alive_participants(self) -> List[Participant]:
    return [p for p in self.participants if p.runtime.hp > 0]

  def players_alive(self) -> List[Participant]:
    return [p for p in self.alive_participants() if p.side == "player"]

  def mobs_alive(self) -> List[Participant]:
    return [p for p in self.alive_participants() if p.side == "mob"]

  def _turn_cycle(self) -> List[Participant]:
    # 1 round = tous les PJ (vivants) puis tous les mobs (vivants)
    return self.players_alive() + self.mobs_alive()

  def current_actor(self) -> Optional[Participant]:
    cycle = self._turn_cycle()
    if not cycle:
      return None
    idx = self.turn_index % len(cycle)
    return cycle[idx]

  def recompute_round(self) -> None:
    cycle = self._turn_cycle()
    if not cycle:
      self.round = 1
      return
    self.round = (self.turn_index // len(cycle)) + 1

  def next_turn(self) -> None:
    self.turn_index += 1
    self.recompute_round()

  def to_dict(self) -> Dict[str, Any]:
    return {
      "encounter_id": self.encounter_id,
      "created_ts": self.created_ts,
      "turn_index": self.turn_index,
      "round": self.round,
      "participants": [
        {"id": p.id, "side": p.side, "runtime": asdict(p.runtime)} for p in self.participants
      ],
      "log": [e.to_dict() for e in self.log],
    }

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "EncounterState":
    stt = EncounterState(
      encounter_id=d.get("encounter_id", str(uuid.uuid4())),
      created_ts=float(d.get("created_ts", time.time())),
    )
    stt.turn_index = int(d.get("turn_index", 0))
    stt.round = int(d.get("round", 1))

    parts: List[Participant] = []
    for pd in d.get("participants", []):
      rd = pd["runtime"]
      rt = RuntimeEntity(**rd)
      parts.append(Participant(id=pd["id"], side=pd["side"], runtime=rt))
    stt.participants = parts

    stt.log = [ActionLogEntry(**ld) for ld in d.get("log", [])]
    stt.recompute_round()
    return stt
