from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .models import Compendium, Monster, MonsterVariant, Skill


# ============================================================
# Utils
# ============================================================

_RE_WS = re.compile(r"[ \t]+")

def _norm(s: str) -> str:
  return _RE_WS.sub(" ", (s or "").strip())


def _as_float(s: str) -> float:
  s = (s or "").strip()
  s = s.replace(",", ".")
  return float(s)


def _as_int(s: str) -> int:
  return int(float((s or "").strip().replace(",", ".")))


def _strip_md(s: str) -> str:
  # enlève un peu de markdown courant (gras/italique)
  s = re.sub(r"[*_`]", "", s or "")
  return _norm(s)


def _safe_key(name: str, existing: Dict[str, Any]) -> str:
  """
  Évite d'écraser un monstre/skill si le même nom apparaît plusieurs fois.
  """
  base = name
  if base not in existing:
    return base
  i = 2
  while f"{base} ({i})" in existing:
    i += 1
  return f"{base} ({i})"


# ============================================================
# Parsing Bestiaire.md (Monstres)
# ============================================================

# Exemples ciblés dans Bestiaire.md :
# ### **Lapin végétal** (Lvl 1-5)
# **Niveau 1:**
# - **HP:** 10/10
# - **MP:** 5/5
# - **STR:** 3
# ...
#
# Autres champs possibles autour :
# - Rareté / Zone / Drops / Compétences (listes)

_RE_MONSTER_HEADER = re.compile(
  r"^\s*###\s*\*\*(?P<name>.+?)\*\*\s*(?:\((?P<range>Lvl\s*[0-9]+(?:\s*-\s*[0-9]+)?)\))?\s*$",
  re.IGNORECASE,
)

_RE_PALIER_HEADER = re.compile(r"^\s*##\s*.*PALIER\s*(?P<pal>\d+).*$", re.IGNORECASE)

_RE_LEVEL_BLOCK = re.compile(r"^\s*\*\*\s*Niveau\s*(?P<lvl>\d+)\s*:\s*\*\*\s*$", re.IGNORECASE)

# - **HP:** 10/10
# - **MP:** 5/5
_RE_HP_MP = re.compile(
  r"^\s*-\s*\*\*(?P<k>HP|MP)\s*:\*\*\s*(?P<cur>[0-9]+(?:[.,][0-9]+)?)\s*/\s*(?P<max>[0-9]+(?:[.,][0-9]+)?)\s*$",
  re.IGNORECASE,
)

# - **STR:** 3
_RE_STAT = re.compile(
  r"^\s*-\s*\*\*(?P<k>STR|AGI|INT|DEX|VIT)\s*:\*\*\s*(?P<v>[0-9]+(?:[.,][0-9]+)?)\s*$",
  re.IGNORECASE,
)

# Attaque de base (optionnel, si présent)
_RE_BASE_ATK = re.compile(
  r"^\s*-\s*\*\*(?P<k>Attaque\s*de\s*base|Base\s*attack)\s*:\*\*\s*(?P<v>[0-9]+(?:[.,][0-9]+)?)\s*$",
  re.IGNORECASE,
)

# Drops: ligne libre du type: "Drops: A, B, C" OU "- Drops: A, B"
_RE_DROPS = re.compile(r"^\s*(?:-\s*)?(?:Drops?)\s*:\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_ZONE = re.compile(r"^\s*(?:-\s*)?Zone\s*:\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_RARITY = re.compile(r"^\s*(?:-\s*)?Raret[eé]\s*:\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_ABILITIES_H = re.compile(r"^\s*####\s*Comp[eé]tences.*$", re.IGNORECASE)
_RE_BULLET = re.compile(r"^\s*-\s+(?P<v>.+?)\s*$")


def parse_monsters_bestiaire(md_text: str) -> Dict[str, Monster]:
  """
  Construit monsters[name] = Monster(...)
  - Variants: dict[int, MonsterVariant]
  - palier détecté via "## PALIER X"
  """
  monsters: Dict[str, Monster] = {}

  current_palier: Optional[str] = None

  cur_monster: Optional[Monster] = None
  cur_key: Optional[str] = None

  cur_level: Optional[int] = None
  cur_hp_max: Optional[float] = None
  cur_mp_max: Optional[float] = None
  cur_stats: Dict[str, float] = {}
  cur_base_attack: Optional[float] = None

  in_abilities = False
  abilities_buf: List[str] = []

  def flush_level() -> None:
    nonlocal cur_level, cur_hp_max, cur_mp_max, cur_stats, cur_base_attack
    if cur_monster is None or cur_level is None:
      return

    # si HP/MP absents, on met 0
    hp_max = float(cur_hp_max or 0.0)
    mp_max = float(cur_mp_max or 0.0)

    v = MonsterVariant(
      level=int(cur_level),
      hp_max=hp_max,
      mp_max=mp_max,
      STR=float(cur_stats.get("STR", 0.0)),
      AGI=float(cur_stats.get("AGI", 0.0)),
      INT=float(cur_stats.get("INT", 0.0)),
      DEX=float(cur_stats.get("DEX", 0.0)),
      VIT=float(cur_stats.get("VIT", 0.0)),
      base_attack=(float(cur_base_attack) if cur_base_attack is not None else None),
      extra=None,
    )
    if cur_monster.variants is None:
      cur_monster.variants = {}
    cur_monster.variants[int(cur_level)] = v

    # reset bloc niveau
    cur_level = None
    cur_hp_max = None
    cur_mp_max = None
    cur_stats = {}
    cur_base_attack = None

  def flush_monster() -> None:
    nonlocal cur_monster, cur_key, in_abilities, abilities_buf
    if cur_monster is None:
      return
    flush_level()

    if abilities_buf:
      cur_monster.abilities = list(dict.fromkeys([_strip_md(a) for a in abilities_buf if _strip_md(a)]))
    abilities_buf = []
    in_abilities = False

    # sécurise variants
    if cur_monster.variants is None:
      cur_monster.variants = {}

    monsters[cur_key or cur_monster.name] = cur_monster
    cur_monster = None
    cur_key = None

  lines = md_text.splitlines()
  for raw in lines:
    line = raw.rstrip("\n")

    m_pal = _RE_PALIER_HEADER.match(line)
    if m_pal:
      current_palier = f"Palier {int(m_pal.group('pal'))}"
      continue

    m_head = _RE_MONSTER_HEADER.match(line)
    if m_head:
      # nouveau monstre -> flush précédent
      flush_monster()

      name = _strip_md(m_head.group("name"))
      lr = _strip_md(m_head.group("range") or "")

      cur_monster = Monster(
        name=name,
        palier=current_palier,
        level_range=(lr.replace("Lvl", "").strip() if lr else None) if lr else (m_head.group("range") or None),
        rarity=None,
        zone=None,
        drops=None,
        abilities=None,
        variants={},
      )
      cur_key = _safe_key(cur_monster.name, monsters)
      continue

    if cur_monster is None:
      continue

    # abilités
    if _RE_ABILITIES_H.match(line):
      in_abilities = True
      continue

    if in_abilities:
      b = _RE_BULLET.match(line)
      if b:
        abilities_buf.append(_strip_md(b.group("v")))
        continue
      # stop abilities section on empty line or next header
      if not _norm(line) or line.lstrip().startswith("#"):
        in_abilities = False

    # champs libres (zone/rarity/drops)
    m_zone = _RE_ZONE.match(line)
    if m_zone:
      cur_monster.zone = _strip_md(m_zone.group("v"))
      continue

    m_r = _RE_RARITY.match(line)
    if m_r:
      cur_monster.rarity = _strip_md(m_r.group("v"))
      continue

    m_d = _RE_DROPS.match(line)
    if m_d:
      raw_d = _strip_md(m_d.group("v"))
      parts = [p.strip() for p in re.split(r"[;,]", raw_d) if p.strip()]
      cur_monster.drops = parts or None
      continue

    # bloc niveau
    m_lvl = _RE_LEVEL_BLOCK.match(line)
    if m_lvl:
      flush_level()
      cur_level = int(m_lvl.group("lvl"))
      continue

    # stats dans un bloc niveau (si cur_level défini)
    if cur_level is not None:
      m_hm = _RE_HP_MP.match(line)
      if m_hm:
        k = m_hm.group("k").upper()
        vmax = _as_float(m_hm.group("max"))
        if k == "HP":
          cur_hp_max = vmax
        else:
          cur_mp_max = vmax
        continue

      m_s = _RE_STAT.match(line)
      if m_s:
        k = m_s.group("k").upper()
        cur_stats[k] = _as_float(m_s.group("v"))
        continue

      m_ba = _RE_BASE_ATK.match(line)
      if m_ba:
        cur_base_attack = _as_float(m_ba.group("v"))
        continue

  # fin fichier
  flush_monster()
  return monsters


# ============================================================
# Parsing Skills (palier1..6.md)
# ============================================================

# Formes fréquentes dans tes fichiers:
# ### Détection de mana
# - **Description:** ...
# - **Coût:** ...
# - **Condition:** ...
#
# ou variantes:
# - **Coût MP:** ...
# - **Coût:** 10 MP
# - **Condition:** ...

_RE_SKILL_PALIER = re.compile(r"^\s*#.*PALIER\s*(?P<pal>\d+).*$", re.IGNORECASE)
_RE_SKILL_CAT = re.compile(r"^\s*##\s*(?P<cat>.+?)\s*$")
_RE_SKILL_NAME = re.compile(r"^\s*###\s*(?P<name>.+?)\s*$")

_RE_DESC = re.compile(r"^\s*-\s*\*\*Description\s*:\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_COST = re.compile(r"^\s*-\s*\*\*(?:Co[uû]t(?:\s*MP)?|Cost(?:\s*MP)?)\s*:\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_COND = re.compile(r"^\s*-\s*\*\*Condition\s*:\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)


def parse_skills_md(md_text: str) -> Dict[str, Skill]:
  skills: Dict[str, Skill] = {}

  palier: Optional[str] = None
  category: Optional[str] = None

  cur: Optional[Skill] = None

  def flush() -> None:
    nonlocal cur
    if cur is None:
      return
    key = _safe_key(cur.name, skills)
    skills[key] = cur
    cur = None

  for raw in md_text.splitlines():
    line = raw.rstrip("\n")

    m_pal = _RE_SKILL_PALIER.match(line)
    if m_pal:
      palier = f"Palier {int(m_pal.group('pal'))}"
      continue

    m_cat = _RE_SKILL_CAT.match(line)
    if m_cat:
      category = _strip_md(m_cat.group("cat"))
      continue

    m_name = _RE_SKILL_NAME.match(line)
    if m_name:
      flush()
      nm = _strip_md(m_name.group("name"))
      cur = Skill(
        name=nm,
        category=category,
        description=None,
        cost_mp=None,
        condition=None,
        palier=palier,
      )
      continue

    if cur is None:
      continue

    m_d = _RE_DESC.match(line)
    if m_d:
      cur.description = _strip_md(m_d.group("v"))
      continue

    m_c = _RE_COST.match(line)
    if m_c:
      cur.cost_mp = _strip_md(m_c.group("v"))
      continue

    m_cond = _RE_COND.match(line)
    if m_cond:
      cur.condition = _strip_md(m_cond.group("v"))
      continue

  flush()
  return skills


# ============================================================
# Build compendium from files
# ============================================================

def build_compendium_from_md(bestiaire_path: Path, skill_paths: List[Path]) -> Compendium:
  """
  Construit un Compendium complet depuis:
    - Bestiaire.md (monstres + variants)
    - palier1..6.md (skills)

  Répare tes cas "skills manquants" en:
    - acceptant des formats légèrement différents (Coût / Coût MP)
    - évitant les écrasements de noms (suffixe (2), (3)...)
  """
  best_text = bestiaire_path.read_text(encoding="utf-8")
  monsters = parse_monsters_bestiaire(best_text)

  skills: Dict[str, Skill] = {}
  for p in skill_paths:
    if not p.exists():
      continue
    md = p.read_text(encoding="utf-8")
    part = parse_skills_md(md)
    # merge en évitant overwrite
    for k, v in part.items():
      key = _safe_key(v.name, skills)
      skills[key] = v

  # IMPORTANT: Compendium.skills est Dict[str, Skill]
  # Dans l'UI tu utilises sorted(comp.skills.keys()) -> OK.
  return Compendium(monsters=monsters, skills=skills)


# ------------------------------------------------------------
# Compat: si ton code appelait déjà un parseur existant
# ------------------------------------------------------------

def load_compendium(bestiaire_md: str, skills_md_list: List[str]) -> Compendium:
  """
  Variante "string-in" (pratique pour tests).
  """
  monsters = parse_monsters_bestiaire(bestiaire_md)
  skills: Dict[str, Skill] = {}
  for md in skills_md_list:
    part = parse_skills_md(md)
    for _, v in part.items():
      key = _safe_key(v.name, skills)
      skills[key] = v
  return Compendium(monsters=monsters, skills=skills)