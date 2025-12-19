from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class Entity:
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
  def from_dict(d: Dict[str, Any]) -> "Entity":
    e = Entity(
      name=d["name"],
      kind=d.get("kind", "PJ"),
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
    e.ensure_current()
    return e

  def to_dict(self) -> Dict[str, Any]:
    self.ensure_current()
    return asdict(self)
