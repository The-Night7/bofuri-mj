import re
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Union

from .models import Compendium, Monster, MonsterVariant, Skill


# ----------------------------
# Regex
# ----------------------------
MONSTER_HEADER_RE = re.compile(
  r"^###\s+\*\*(?P<name>.+?)\*\*(?:\s*\((?P<meta>[^)]*)\))?\s*(?P<tail>.*)$"
)
LEVEL_BLOCK_RE = re.compile(r"^\*\*Niveau\s+(?P<lvl>\d+)\s*:\*\*\s*$", re.IGNORECASE)
STAT_LINE_RE = re.compile(r"^\s*-\s+\*\*(?P<key>[^*]+)\*\*\s*:\s*(?P<val>.+?)\s*$")
PALIER_RE = re.compile(r"^##\s+Palier\s+(?P<n>\d+)\s*$", re.IGNORECASE)
SKILL_HEADER_RE = re.compile(r"^###\s+\*\*(?P<name>.+?)\*\*\s*$")


# ----------------------------
# Helpers
# ----------------------------
def _extract_numbers(s: str) -> List[int]:
  return [int(x) for x in re.findall(r"\d+", s)]


def _parse_monster_meta(meta: Optional[str], tail: str) -> Tuple[Optional[str], Optional[str]]:
  if not meta:
    if "👑" in (tail or ""):
      return None, "Boss"
    return None, None

  m = meta.strip()
  lower = m.lower()

  level_range: Optional[str] = None
  rng = re.search(r"(\d+)\s*-\s*(\d+)", m)
  if rng:
    level_range = f"{int(rng.group(1))}-{int(rng.group(2))}"
  else:
    nums = _extract_numbers(m)
    if nums:
      level_range = str(nums[0])

  rarity: Optional[str] = None
  cleaned = re.sub(r"\b(lvl|level)\b", " ", lower, flags=re.IGNORECASE)
  cleaned = re.sub(r"[\d\-]+", " ", cleaned)
  cleaned = re.sub(r"\s+", " ", cleaned).strip()
  if cleaned:
    if "élite" in cleaned or "elite" in cleaned:
      rarity = "Élite"
    else:
      rarity = cleaned

  if "👑" in (tail or "") and not rarity:
    rarity = "Boss"

  return level_range, rarity


def _infer_default_level(level_range: Optional[str]) -> int:
  if not level_range:
    return 1
  s = str(level_range).strip().lower().replace("lvl", "").strip()
  if "-" in s:
    left = s.split("-", 1)[0].strip()
    try:
      return int(left)
    except Exception:
      return 1
  try:
    return int(s)
  except Exception:
    return 1


def _ensure_implicit_variant(current: Monster) -> int:
  if current.variants is None:
    current.variants = {}
  if current.variants:
    return sorted(current.variants.keys())[0]

  lvl = _infer_default_level(current.level_range)
  current.variants[lvl] = MonsterVariant(
    level=lvl,
    hp_max=0, mp_max=0,
    STR=0, AGI=0, INT=0, DEX=0, VIT=0,
    base_attack=None,
    extra={}
  )
  return lvl


def _parse_base_attack(val: str) -> Optional[float]:
  nums = re.findall(r"[\d]+(?:\.[\d]+)?", val.replace(",", "."))
  if not nums:
    return None
  try:
    return float(nums[0])
  except Exception:
    return None


def _pick_first_existing(base_dir: Path, candidates: List[str]) -> Path:
  for name in candidates:
    p = base_dir / name
    if p.exists() and p.is_file():
      return p
  raise FileNotFoundError(
    "Impossible de trouver le fichier. Essayé: "
    + ", ".join(str(base_dir / c) for c in candidates)
  )


def _try_pick_first_existing(base_dir: Path, candidates: List[str]) -> Optional[Path]:
  for name in candidates:
    p = base_dir / name
    if p.exists() and p.is_file():
      return p
  return None


# ----------------------------
# Parsing
# ----------------------------
def parse_bestiaire(md_text: str) -> Dict[str, Monster]:
  current_palier: Optional[str] = None
  monsters: Dict[str, Monster] = {}

  current: Optional[Monster] = None
  current_level: Optional[int] = None

  for raw in md_text.splitlines():
    line = raw.rstrip("\n")
    if not line.strip():
      continue

    pm = PALIER_RE.match(line.strip())
    if pm:
      current_palier = f"Palier {int(pm.group('n'))}"
      continue

    hm = MONSTER_HEADER_RE.match(line.strip())
    if hm:
      name = hm.group("name").strip()
      meta = hm.group("meta")
      tail = hm.group("tail") or ""
      level_range, rarity = _parse_monster_meta(meta, tail)

      current = Monster(
        name=name,
        palier=current_palier,
        level_range=level_range,
        rarity=rarity,
        zone=None,
        drops=None,
        abilities=None,
        variants={}
      )
      monsters[name] = current
      current_level = None
      continue

    if current is None:
      continue

    lm = LEVEL_BLOCK_RE.match(line.strip())
    if lm:
      lvl = int(lm.group("lvl"))
      current_level = lvl
      if current.variants is None:
        current.variants = {}
      current.variants[lvl] = MonsterVariant(
        level=lvl,
        hp_max=0, mp_max=0,
        STR=0, AGI=0, INT=0, DEX=0, VIT=0,
        base_attack=None,
        extra={}
      )
      continue

    sm = STAT_LINE_RE.match(line)
    if sm:
      key = sm.group("key").strip()
      val = sm.group("val").strip()
      k = key.lower()

      if current_level is None:
        current_level = _ensure_implicit_variant(current)

      v = current.variants[current_level]

      if k == "hp":
        try:
          v.hp_max = float(val.split("/")[1].replace(",", "."))
        except Exception:
          pass
        continue

      if k == "mp":
        try:
          v.mp_max = float(val.split("/")[1].replace(",", "."))
        except Exception:
          pass
        continue

      if k in {"str", "agi", "int", "dex", "vit"}:
        try:
          setattr(v, k.upper(), float(val.replace(",", ".")))
        except Exception:
          pass
        continue

      if "attaque de base" in k:
        v.base_attack = _parse_base_attack(val)
        continue

      if k == "drop":
        current.drops = [x.strip() for x in val.split(",") if x.strip()]
        continue

      if k == "zone":
        current.zone = val
        continue

      if k.startswith("compétences") or k.startswith("competences"):
        current.abilities = current.abilities or []
        if val and val != "—":
          current.abilities.append(val)
        continue

      v.extra = v.extra or {}
      v.extra[k] = val
      continue

    if line.strip().startswith("- ") and current is not None:
      if current.abilities is not None:
        current.abilities.append(line.strip()[2:].strip())
      continue

  return monsters


def parse_skills(md_text: str) -> Dict[str, Skill]:
  skills: Dict[str, Skill] = {}
  current: Optional[Skill] = None

  for raw in md_text.splitlines():
    line = raw.rstrip("\n")
    if not line.strip():
      continue

    hm = SKILL_HEADER_RE.match(line.strip())
    if hm:
      name = hm.group("name").strip()
      current = Skill(name=name)
      skills[name] = current
      continue

    if current is None:
      continue

    sm = STAT_LINE_RE.match(line)
    if sm:
      key = sm.group("key").strip().lower()
      val = sm.group("val").strip()

      if key in {"catégorie", "categorie"}:
        current.category = val
      elif key == "description":
        current.description = val
      elif key in {"coût", "cout", "mp", "coût mp", "cout mp"}:
        current.cost_mp = val
      elif key == "condition":
        current.condition = val
      elif key == "palier":
        current.palier = val
      continue

  return skills


def parse_compendium(bestiaire_md: str, skills_md: str) -> Compendium:
  return Compendium(
    monsters=parse_bestiaire(bestiaire_md),
    skills=parse_skills(skills_md)
  )


# ----------------------------
# API attendue par app.py
# ----------------------------
def build_compendium_from_docs(
  docs_dir_or_bestiaire: Union[str, Path],
  skills_path: Optional[Union[str, Path]] = None,
  encoding: str = "utf-8"
) -> Compendium:
  """
  Supporte 2 signatures:
    1) build_compendium_from_docs(docs_dir)
       -> cherche Bestiaire.md et (optionnel) Skills.md

    2) build_compendium_from_docs(bestiaire_path, skills_path)
       -> lit exactement ces fichiers
  """
  if skills_path is None:
    docs_dir = Path(docs_dir_or_bestiaire)
    if not docs_dir.exists() or not docs_dir.is_dir():
      raise FileNotFoundError(f"docs_dir introuvable ou invalide: {docs_dir}")

    bestiaire_file = _pick_first_existing(
      docs_dir,
      candidates=[
        "Bestiaire.md", "bestiaire.md",
        "Monstres.md", "monstres.md",
        "Mobs.md", "mobs.md",
      ],
    )

    # Skills devient OPTIONNEL
    skills_file = _try_pick_first_existing(
      docs_dir,
      candidates=[
        "Skills.md", "skills.md",
        "Competences.md", "competences.md",
        "Compétences.md",
        "Sorts.md", "sorts.md",
        "Capacites.md", "capacites.md",
        "Capacités.md",
      ],
    )

    bestiaire_md = bestiaire_file.read_text(encoding=encoding)
    skills_md = skills_file.read_text(encoding=encoding) if skills_file else ""
    return parse_compendium(bestiaire_md=bestiaire_md, skills_md=skills_md)

  # Signature 2: chemins explicites
  bestiaire_file = Path(docs_dir_or_bestiaire)
  skills_file = Path(skills_path)
  bestiaire_md = bestiaire_file.read_text(encoding=encoding)
  skills_md = skills_file.read_text(encoding=encoding)
  return parse_compendium(bestiaire_md=bestiaire_md, skills_md=skills_md)
# End of file