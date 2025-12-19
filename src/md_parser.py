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

  # ---- Bestiaire
  bestiary_path = d / "Bestiaire.md"
  if bestiary_path.exists():
    monsters.update(parse_bestiaire(bestiary_path))

  # ---- Skills (priorité tout.md si présent)
  skills_sources = []
  if (d / "tout.md").exists():
    skills_sources.append(d / "tout.md")
  else:
    # fallback : palier1..6 si tout.md absent
    for i in range(1, 7):
      p = d / f"palier{i}.md"
      if p.exists():
        skills_sources.append(p)

  for sp in skills_sources:
    skills.update(parse_skills(sp))

  return Compendium(monsters=monsters, skills=skills)


# ----------------------------
# BESTIAIRE PARSER
# ----------------------------

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

  in_skills_list = False

  def ensure_current_variants():
    nonlocal current
    if current is not None and current.variants is None:
      current.variants = {}

  for raw in lines:
    line = raw.strip()

    # Nouveau monstre
    m = MONSTER_HEADER_RE.match(line)
    if m:
      name = m.group("name").strip()
      lvl_raw = m.group("lvl").strip()  # ex "Lvl 1-10" ou "Lvl 10"
      rest = (m.group("rest") or "").strip()

      rarity = None
      if "monstre rare" in rest.lower():
        rarity = "Monstre Rare"
      elif "boss" in rest.lower():
        rarity = "Boss"

      current = Monster(
        name=name,
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

    # Début bloc Niveau X
    lm = LEVEL_BLOCK_RE.match(line)
    if lm:
      current_level = int(lm.group("lvl"))
      ensure_current_variants()
      current.variants[current_level] = MonsterVariant(
        level=current_level,
        hp_max=0, mp_max=0, STR=0, AGI=0, INT=0, DEX=0, VIT=0,
        base_attack=None,
        extra={}
      )
      in_skills_list = False
      continue

    # Entrée "Compétences:"
    if line.lower().startswith("- **compétences:**") or line.lower().startswith("**compétences:**") or line.lower().startswith("compétences:"):
      in_skills_list = True
      continue

    # Liste de compétences indentée
    if in_skills_list and (line.startswith("- **") or line.startswith("- ")):
      # Exemple: - **Cri de la reine:** Quand PV...
      # ou - **Dard empoisonné:** 30/tour
      # On garde la ligne "propre"
      cleaned = re.sub(r"^\-\s*", "", line).strip()
      current.abilities = current.abilities or []
      current.abilities.append(cleaned)
      continue

    # Ligne de stat générique
    sm = STAT_LINE_RE.match(line)
    if sm and current_level is not None and current.variants and current_level in current.variants:
      key = sm.group("key").strip().lower()
      val = sm.group("val").strip()
      v = current.variants[current_level]

      # HP / MP format "10/10"
      if key == "hp":
        try:
          hpmax = float(val.split("/")[1])
          v.hp_max = hpmax
        except Exception:
          pass
        continue
      if key == "mp":
        try:
          mpmax = float(val.split("/")[1])
          v.mp_max = mpmax
        except Exception:
          pass
        continue

      # Stats
      if key in ["str", "agi", "int", "dex", "vit"]:
        try:
          setattr(v, key.upper(), float(val))
        except Exception:
          pass
        continue

      # Attaque de base
      if "attaque de base" in key:
        try:
          v.base_attack = float(re.findall(r"[\d\.]+", val)[0])
        except Exception:
          v.base_attack = None
        continue

      # Drop / Zone
      if key == "drop":
        # "Herbes fraîches, Bois sec"
        drops = [x.strip() for x in val.split(",") if x.strip()]
        current.drops = drops
        continue

      if key == "zone":
        current.zone = val
        continue

      # Autres lignes (ex: "Crachat de poison: 15/tour")
      # On stocke dans extra
      v.extra = v.extra or {}
      v.extra[key] = val
      continue

    # Drop/Zone hors bloc niveau (rare) : on tente quand même
    sm2 = STAT_LINE_RE.match(line)
    if sm2 and current_level is None:
      key = sm2.group("key").strip().lower()
      val = sm2.group("val").strip()
      if key == "drop":
        current.drops = [x.strip() for x in val.split(",") if x.strip()]
      elif key == "zone":
        current.zone = val
      continue

    # fin implicite de compétences si ligne vide
    if in_skills_list and line == "":
      in_skills_list = False

  # Nettoyage: enlever variantes vides
  for m in monsters.values():
    if m.variants:
      for lvl, v in list(m.variants.items()):
        if v.hp_max == 0 and v.mp_max == 0 and v.STR == 0 and v.VIT == 0:
          # on garde quand même si extra présent
          if not v.extra:
            del m.variants[lvl]

  return monsters


# ----------------------------
# SKILLS PARSER
# ----------------------------

SKILL_TITLE_RE = re.compile(r"^####\s+\*\*(?P<name>.+?)\*\*\s*$")
FIELD_RE = re.compile(r"^\-\s+\*\*(?P<key>[^*]+)\:\*\*\s*(?P<val>.+?)\s*$")
CATEGORY_RE = re.compile(r"^###\s+.+\*\*(?P<cat>.+?)\*\*.*$")
PALIER_RE = re.compile(r"^##\s+.*PALIER\s+(?P<p>\d+).*$", re.IGNORECASE)


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

    pm = PALIER_RE.match(line)
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
        # fallback: concat dans description
        if current.description:
          current.description += f" | {fm.group('key')}: {v}"
        else:
          current.description = f"{fm.group('key')}: {v}"
      continue

  return skills
