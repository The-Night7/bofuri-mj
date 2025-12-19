import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .models import Compendium, Monster, MonsterVariant, Skill


def _read_text(path: Path) -> str:
  return path.read_text(encoding="utf-8", errors="ignore")


def build_compendium_from_docs(docs_dir: str) -> Compendium:
  d = Path(docs_dir)
  monsters: Dict[str, Monster] = {}
  skills: Dict[str, Skill] = {}

  bestiary_path = d / "Bestiaire.md"
  if bestiary_path.exists():
    monsters.update(parse_bestiaire(bestiary_path))

    # Compléter les niveaux manquants (progressif min→max)
    for m in monsters.values():
      if m.variants:
        m.variants = densify_variants(m.variants)

  # Skills
  skills_sources = []
  if (d / "tout.md").exists():
    skills_sources.append(d / "tout.md")
  else:
    for i in range(1, 7):
      p = d / f"palier{i}.md"
      if p.exists():
        skills_sources.append(p)

  for sp in skills_sources:
    skills.update(parse_skills(sp))

  return Compendium(monsters=monsters, skills=skills)


# ----------------------------
# BESTIAIRE PARSER (avec Palier)
# ----------------------------

PALIER_RE = re.compile(r"^##\s+.*PALIER\s+(?P<p>\d+).*$", re.IGNORECASE)
MONSTER_HEADER_RE = re.compile(
  r"^###\s+\*\*(?P<name>.+?)\*\*\s*\((?P<lvl>Lvl\s*[^)]+)\)\s*(?P<rest>.*)$",
  re.IGNORECASE
)
LEVEL_BLOCK_RE = re.compile(r"^\*\*Niveau\s+(?P<lvl>\d+)\:\*\*\s*$", re.IGNORECASE)
STAT_LINE_RE = re.compile(r"^\-\s+\*\*(?P<key>[^*]+)\:\*\*\s*(?P<val>.+?)\s*$")


def parse_bestiaire(path: Path) -> Dict[str, Monster]:
  text = _read_text(path)
  lines = text.splitlines()

  monsters: Dict[str, Monster] = {}
  current: Optional[Monster] = None
  current_level: Optional[int] = None
  current_palier: Optional[str] = None

  in_skills_list = False

  def ensure_variants():
    nonlocal current
    if current is not None and current.variants is None:
      current.variants = {}

  for raw in lines:
    line = raw.strip()

    pm = PALIER_RE.match(line)
    if pm:
      current_palier = f"Palier {pm.group('p')}"
      continue

    m = MONSTER_HEADER_RE.match(line)
    if m:
      name = m.group("name").strip()
      lvl_raw = m.group("lvl").strip()
      rest = (m.group("rest") or "").strip()

      rarity = None
      if "monstre rare" in rest.lower():
        rarity = "Monstre Rare"
      elif "boss" in rest.lower():
        rarity = "Boss"

      current = Monster(
        name=name,
        palier=current_palier,
        level_range=lvl_raw.replace("Lvl", "").strip(),
        rarity=rarity,
        zone=None,
        drops=None,
        abilities=[],
        variants={}
      )
      monsters[name] = current
      current_level = None
      in_skills_list = False
      continue

    if current is None:
      continue

    lm = LEVEL_BLOCK_RE.match(line)
    if lm:
      current_level = int(lm.group("lvl"))
      ensure_variants()
      current.variants[current_level] = MonsterVariant(
        level=current_level,
        hp_max=0, mp_max=0, STR=0, AGI=0, INT=0, DEX=0, VIT=0,
        base_attack=None,
        extra={}
      )
      in_skills_list = False
      continue

    if line.lower().startswith("- **compétences:**") or line.lower().startswith("**compétences:**") or line.lower().startswith("compétences:"):
      in_skills_list = True
      continue

    if in_skills_list and (line.startswith("- **") or line.startswith("- ")):
      cleaned = re.sub(r"^\-\s*", "", line).strip()
      current.abilities = current.abilities or []
      current.abilities.append(cleaned)
      continue

    sm = STAT_LINE_RE.match(line)
    if sm and current_level is not None and current.variants and current_level in current.variants:
      key = sm.group("key").strip().lower()
      val = sm.group("val").strip()
      v = current.variants[current_level]

      if key == "hp":
        try:
          v.hp_max = float(val.split("/")[1])
        except Exception:
          pass
        continue

      if key == "mp":
        try:
          v.mp_max = float(val.split("/")[1])
        except Exception:
          pass
        continue

      if key in ["str", "agi", "int", "dex", "vit"]:
        try:
          setattr(v, key.upper(), float(val))
        except Exception:
          pass
        continue

      if "attaque de base" in key:
        try:
          v.base_attack = float(re.findall(r"[\d\.]+", val)[0])
        except Exception:
          v.base_attack = None
        continue

      if key == "drop":
        current.drops = [x.strip() for x in val.split(",") if x.strip()]
        continue

      if key == "zone":
        current.zone = val
        continue

      v.extra = v.extra or {}
      v.extra[key] = val
      continue

    # Drop/Zone parfois placés dans "abilities" (chez toi on voit Drop/Zone listés)
    sm2 = STAT_LINE_RE.match(line)
    if sm2 and current_level is None:
      key = sm2.group("key").strip().lower()
      val = sm2.group("val").strip()
      if key == "drop":
        current.drops = [x.strip() for x in val.split(",") if x.strip()]
      elif key == "zone":
        current.zone = val
      continue

    if in_skills_list and line == "":
      in_skills_list = False

  # nettoyage
  for mon in monsters.values():
    if mon.variants:
      for lvl, v in list(mon.variants.items()):
        if v.hp_max == 0 and v.mp_max == 0 and v.STR == 0 and v.VIT == 0 and not v.extra:
          del mon.variants[lvl]

  return monsters


# ----------------------------
# Variants densification (min -> max)
# ----------------------------

def densify_variants(variants: Dict[int, MonsterVariant]) -> Dict[int, MonsterVariant]:
  """
  Si on a (lvl 1) et (lvl 5), crée lvl 2,3,4 par interpolation linéaire.
  Les champs extra: repris du plus proche niveau inférieur.
  """
  lvls = sorted(variants.keys())
  if len(lvls) < 2:
    return variants

  def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

  dense: Dict[int, MonsterVariant] = {}
  for i in range(len(lvls) - 1):
    l1, l2 = lvls[i], lvls[i + 1]
    v1, v2 = variants[l1], variants[l2]
    span = l2 - l1
    for l in range(l1, l2):
      if l == l1:
        dense[l] = v1
        continue
      t = (l - l1) / span
      dense[l] = MonsterVariant(
        level=l,
        hp_max=lerp(v1.hp_max, v2.hp_max, t),
        mp_max=lerp(v1.mp_max, v2.mp_max, t),
        STR=lerp(v1.STR, v2.STR, t),
        AGI=lerp(v1.AGI, v2.AGI, t),
        INT=lerp(v1.INT, v2.INT, t),
        DEX=lerp(v1.DEX, v2.DEX, t),
        VIT=lerp(v1.VIT, v2.VIT, t),
        base_attack=lerp(v1.base_attack or 0.0, v2.base_attack or 0.0, t) if (v1.base_attack is not None or v2.base_attack is not None) else None,
        extra=v1.extra or {}
      )
    dense[l2] = v2

  return {lvl: dense[lvl] for lvl in sorted(dense.keys())}


# ----------------------------
# SKILLS PARSER
# ----------------------------

SKILL_TITLE_RE = re.compile(r"^####\s+\*\*(?P<name>.+?)\*\*\s*$")
FIELD_RE = re.compile(r"^\-\s+\*\*(?P<key>[^*]+)\:\*\*\s*(?P<val>.+?)\s*$")
CATEGORY_RE = re.compile(r"^###\s+.+\*\*(?P<cat>.+?)\*\*.*$")
PALIER_SK_RE = re.compile(r"^##\s+.*PALIER\s+(?P<p>\d+).*$", re.IGNORECASE)


def parse_skills(path: Path) -> Dict[str, Skill]:
  text = _read_text(path)
  lines = text.splitlines()

  skills: Dict[str, Skill] = {}
  current: Optional[Skill] = None
  current_cat: Optional[str] = None
  current_palier: Optional[str] = None

  for raw in lines:
    line = raw.strip()
    if not line:
      continue

    pm = PALIER_SK_RE.match(line)
    if pm:
      current_palier = f"Palier {pm.group('p')}"
      continue

    cm = CATEGORY_RE.match(line)
    if cm:
      current_cat = cm.group("cat").strip()
      continue

    tm = SKILL_TITLE_RE.match(line)
    if tm:
      name = tm.group("name").strip()
      current = Skill(name=name, category=current_cat, palier=current_palier)
      skills[name] = current
      continue

    fm = FIELD_RE.match(line)
    if fm and current is not None:
      k = fm.group("key").strip().lower()
      v = fm.group("val").strip()

      if "description" in k:
        current.description = v
      elif "coût" in k or "cout" in k or "mp" in k:
        current.cost_mp = v
      elif "condition" in k:
        current.condition = v
      else:
        current.description = (current.description + " | " if current.description else "") + f"{fm.group('key')}: {v}"

  return skills
