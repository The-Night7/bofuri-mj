from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List


@dataclass
class RuntimeEntity:
  # Entité "en combat" (PJ ou Monstre variante). Pour les monstres: pas persistée.
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

  # infos bestiaire (affichage + MJ)
  base_attack: Optional[float] = None
  zone: Optional[str] = None
  drops: Optional[List[str]] = None
  abilities: Optional[List[str]] = None

  def reset(self) -> None:
    self.hp = float(self.hp_max)
    self.mp = float(self.mp_max)


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

  # Certaines variantes ont des lignes particulières (poison/tour etc.)
  extra: Optional[Dict[str, Any]] = None


@dataclass
class Monster:
  name: str
  level_range: Optional[str] = None  # ex: "1-10" si présent
  rarity: Optional[str] = None       # ex: "Monstre Rare"
  zone: Optional[str] = None
  drops: Optional[List[str]] = None
  abilities: Optional[List[str]] = None  # liste de lignes "Compétences"

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
      "skills": {k: asdict(v) for k, v in self.skills.items()}
    }

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "Compendium":
    monsters: Dict[str, Monster] = {}
    for name, md in d.get("monsters", {}).items():
      variants = {}
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
          extra=vd.get("extra")
        )
      monsters[name] = Monster(
        name=md.get("name", name),
        level_range=md.get("level_range"),
        rarity=md.get("rarity"),
        zone=md.get("zone"),
        drops=md.get("drops"),
        abilities=md.get("abilities"),
        variants=variants
      )

    skills: Dict[str, Skill] = {}
    for name, sd in d.get("skills", {}).items():
      skills[name] = Skill(**sd)

    return Compendium(monsters=monsters, skills=skills)


@dataclass
class CombatantRef:
  # Référence UI (soit un PJ, soit un monstre + niveau variante)
  ref_type: str  # "player" | "monster"
  ref_name: str
  variant_level: Optional[int] = None

  def to_runtime(self, players: List[Player], compendium: Compendium) -> RuntimeEntity:
    if self.ref_type == "player":
      p = next(x for x in players if x.name == self.ref_name)
      p.ensure_current()
      return RuntimeEntity(
        name=p.name,
        kind="PJ",
        level=p.level,
        hp_max=p.hp_max,
        mp_max=p.mp_max,
        STR=p.STR, AGI=p.AGI, INT=p.INT, DEX=p.DEX, VIT=p.VIT,
        hp=float(p.hp), mp=float(p.mp),
      )

    # Monster
    m = compendium.monsters[self.ref_name]
    lvl = int(self.variant_level or min(m.variants.keys()))
    v = m.variants[lvl]
    return RuntimeEntity(
      name=f"{m.name} (Lvl {lvl})",
      kind="Boss" if (m.rarity and "boss" in m.rarity.lower()) else "Mob",
      level=lvl,
      hp_max=v.hp_max,
      mp_max=v.mp_max,
      STR=v.STR, AGI=v.AGI, INT=v.INT, DEX=v.DEX, VIT=v.VIT,
      hp=float(v.hp_max),
      mp=float(v.mp_max),
      base_attack=v.base_attack,
      zone=m.zone,
      drops=m.drops,
      abilities=m.abilities,
    )

  def apply_runtime_back(self, runtime: RuntimeEntity, players: List[Player]) -> None:
    # Seuls les PJ sont persistants
    if self.ref_type != "player":
      return
    p = next(x for x in players if x.name == self.ref_name)
    p.hp = float(runtime.hp)
    p.mp = float(runtime.mp)
