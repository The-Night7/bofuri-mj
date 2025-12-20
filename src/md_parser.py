from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Compendium, Monster, MonsterVariant, Skill

# ============================================================
# Helpers
# ============================================================

_RE_WS = re.compile(r"[ \t]+")


def _norm(s: str) -> str:
    return _RE_WS.sub(" ", (s or "").strip())


def _strip_md(s: str) -> str:
    s = re.sub(r"[*_`]", "", s or "")
    return _norm(s)


def _as_float(s: str) -> Optional[float]:
    s = _strip_md(s).replace(",", ".")
    if not s or "?" in s:
        return None
    m = re.search(r"[0-9]+(?:\.[0-9]+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _safe_key(name: str, existing: Dict[str, Any]) -> str:
    base = name
    if base not in existing:
        return base
    i = 2
    while f"{base} ({i})" in existing:
        i += 1
    return f"{base} ({i})"


# ============================================================
# MONSTRES — PATCH (Bestiaire.md)
# ============================================================

_RE_PALIER = re.compile(r"^\s*#{1,4}.*PALIER\s*(?P<pal>\d+)\b.*$", re.IGNORECASE)

_RE_SECTION_BAD = re.compile(
    r"(PALIER\s*\d+|BOSS|DONJON|STATISTIQUES|L[EÉ]GENDE|SYMBOL(?:ES)?|TYPES\s+DE\s+ZONES)",
    re.IGNORECASE
)

# On exige **Nom** pour éviter de matcher les titres de sections (BOSS etc.)
_RE_MONSTER_HEADER = re.compile(
    r"^\s*#{2,4}\s*(?:[^\w]*\s*)?\*\*(?P<name>.+?)\*\*\s*(?:\((?P<range>[^)]+)\))?\s*(?:👑)?\s*(?:\*.*\*)?\s*$"
)

_RE_LEVEL = re.compile(r"^\s*\*\*\s*Niveau\s*(?P<lvl>\d+)\s*(?:\([^)]*\))?\s*:\s*\*\*\s*$", re.IGNORECASE)
_RE_PHASE = re.compile(r"^\s*\*\*\s*(?P<label>(?:Phase|Version)\s*[^:]+)\s*:\s*\*\*\s*$", re.IGNORECASE)

# Ton format réel: "- **HP:** 10/10" (":" dans le gras)
_RE_HP_MP = re.compile(r"^\s*-\s*\*\*(?P<k>HP|MP)\s*:\s*\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_STAT = re.compile(r"^\s*-\s*\*\*(?P<k>STR|AGI|INT|DEX|VIT)\s*:\s*\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_BASE_ATK = re.compile(r"^\s*-\s*\*\*Attaque\s*de\s*base\s*:\s*\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_DROP = re.compile(r"^\s*-\s*\*\*Drop\s*:\s*\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)
_RE_ZONE = re.compile(r"^\s*-\s*\*\*Zone\s*:\s*\*\*\s*(?P<v>.+?)\s*$", re.IGNORECASE)

_RE_ABILITIES_H = re.compile(r"^\s*-\s*\*\*Comp[eé]tences\s*:\s*\*\*\s*$", re.IGNORECASE)
_RE_ABILITY_ITEM = re.compile(r"^\s*-\s*\*\*(?P<name>.+?)\s*:\s*\*\*\s*(?P<desc>.+?)\s*$")

_RE_KV_ANY = re.compile(r"^\s*-\s*\*\*(?P<k>.+?)\s*:\s*\*\*\s*(?P<v>.+?)\s*$")

# ============================================================
# SKILLS — Expressions régulières pour les compétences
# ============================================================

_RE_SKILL_HEADER = re.compile(r"^\s*#{1,4}\s*\*\*(?P<name>.+?)\*\*\s*$")
_RE_SKILL_CATEGORY = re.compile(r"^\s*-\s*\*\*Cat[ée]gorie\s*:\s*\*\*\s*(?P<cat>.+?)\s*$", re.IGNORECASE)
_RE_SKILL_COST = re.compile(r"^\s*-\s*\*\*Co[ûu]t\s*(?:MP|PM)\s*:\s*\*\*\s*(?P<cost>.+?)\s*$", re.IGNORECASE)
_RE_SKILL_CONDITION = re.compile(r"^\s*-\s*\*\*Condition\s*:\s*\*\*\s*(?P<cond>.+?)\s*$", re.IGNORECASE)
_RE_SKILL_DESCRIPTION = re.compile(r"^\s*-\s*\*\*Description\s*:\s*\*\*\s*(?P<desc>.+?)\s*$", re.IGNORECASE)


def parse_monsters_bestiaire(md_text: str) -> Dict[str, Monster]:
    monsters: Dict[str, Monster] = {}

    current_palier: Optional[str] = None

    cur_monster: Optional[Monster] = None
    cur_key: Optional[str] = None

    cur_level: Optional[int] = None
    cur_label: Optional[str] = None
    cur_hp_max: Optional[float] = None
    cur_mp_max: Optional[float] = None
    cur_stats: Dict[str, float] = {}
    cur_base_attack: Optional[str] = None
    cur_extra: Dict[str, str] = {}
    cur_abilities: List[str] = []

    artificial_level = 0

    def _ensure_variant_level() -> int:
        nonlocal artificial_level, cur_level
        if cur_level is not None:
            return cur_level
        artificial_level += 1
        cur_level = 10_000 + artificial_level
        return cur_level

    def flush_variant() -> None:
        nonlocal cur_level, cur_label, cur_hp_max, cur_mp_max, cur_stats, cur_base_attack, cur_extra, cur_abilities
        if cur_monster is None:
            return

        if (
                cur_level is None
                and cur_label is None
                and cur_hp_max is None
                and cur_mp_max is None
                and not cur_stats
                and cur_base_attack is None
                and not cur_extra
                and not cur_abilities
        ):
            return

        lvl = _ensure_variant_level()

        v = MonsterVariant(
            level=int(lvl),
            hp_max=float(cur_hp_max or 0.0),
            mp_max=float(cur_mp_max or 0.0),
            STR=float(cur_stats.get("STR", 0.0)),
            AGI=float(cur_stats.get("AGI", 0.0)),
            INT=float(cur_stats.get("INT", 0.0)),
            DEX=float(cur_stats.get("DEX", 0.0)),
            VIT=float(cur_stats.get("VIT", 0.0)),
            base_attack=cur_base_attack,
            extra={
                      **({"label": cur_label} if cur_label else {}),
                      **(cur_extra if cur_extra else {}),
                      **({"abilities": cur_abilities} if cur_abilities else {}),
                  } or None,
        )

        if cur_monster.variants is None:
            cur_monster.variants = {}
        cur_monster.variants[int(lvl)] = v

        cur_level = None
        cur_label = None
        cur_hp_max = None
        cur_mp_max = None
        cur_stats = {}
        cur_base_attack = None
        cur_extra = {}
        cur_abilities = []

    def flush_monster() -> None:
        nonlocal cur_monster, cur_key, artificial_level
        if cur_monster is None:
            return
        flush_variant()
        if cur_monster.variants is None:
            cur_monster.variants = {}
        monsters[cur_key or cur_monster.name] = cur_monster
        cur_monster = None
        cur_key = None
        artificial_level = 0

    for raw in md_text.splitlines():
        line = raw.rstrip("\n")

        m_pal = _RE_PALIER.match(line)
        if m_pal:
            current_palier = f"Palier {int(m_pal.group('pal'))}"
            continue

        m_h = _RE_MONSTER_HEADER.match(line)
        if m_h:
            if _RE_SECTION_BAD.search(line):
                continue

            flush_monster()

            name = _strip_md(m_h.group("name"))
            lvl_range = _strip_md(m_h.group("range") or "") or None

            cur_monster = Monster(
                name=name,
                palier=current_palier,
                level_range=lvl_range,
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

        m_lvl = _RE_LEVEL.match(line)
        if m_lvl:
            flush_variant()
            cur_level = int(m_lvl.group("lvl"))
            continue

        m_ph = _RE_PHASE.match(line)
        if m_ph:
            flush_variant()
            cur_label = _strip_md(m_ph.group("label"))
            cur_level = None
            continue

        if _RE_ABILITIES_H.match(line):
            continue

        m_ai = _RE_ABILITY_ITEM.match(line)
        if m_ai:
            nm = _strip_md(m_ai.group("name"))
            ds = _strip_md(m_ai.group("desc"))
            cur_abilities.append(f"{nm}: {ds}")
            continue

        m_drop = _RE_DROP.match(line)
        if m_drop:
            raw_d = _strip_md(m_drop.group("v"))
            parts = [p.strip() for p in re.split(r"[,;/]", raw_d) if p.strip()]
            if parts:
                cur_monster.drops = parts
            continue

        m_zone = _RE_ZONE.match(line)
        if m_zone:
            z = _strip_md(m_zone.group("v"))
            if z:
                cur_monster.zone = z
            continue

        m_hpm = _RE_HP_MP.match(line)
        if m_hpm:
            k = m_hpm.group("k").upper()
            v = _strip_md(m_hpm.group("v"))
            if "/" in v:
                vmax = _as_float(v.split("/", 1)[1])
            else:
                vmax = _as_float(v)
            if k == "HP" and vmax is not None:
                cur_hp_max = vmax
            if k == "MP" and vmax is not None:
                cur_mp_max = vmax
            continue

        m_stat = _RE_STAT.match(line)
        if m_stat:
            k = m_stat.group("k").upper()
            val = _as_float(m_stat.group("v"))
            if val is not None:
                cur_stats[k] = val
            continue

        m_ba = _RE_BASE_ATK.match(line)
        if m_ba:
            cur_base_attack = _strip_md(m_ba.group("v"))
            continue

        m_kv = _RE_KV_ANY.match(line)
        if m_kv:
            k = _strip_md(m_kv.group("k"))
            v = _strip_md(m_kv.group("v"))
            if k.lower() in ("hp", "mp", "str", "agi", "int", "dex", "vit", "attaque de base", "drop", "zone",
                             "compétences", "competences"):
                continue
            _ensure_variant_level()
            cur_extra[k] = v
            continue

    flush_monster()
    return monsters


# ============================================================
# Skills - Implémentation du parseur de compétences
# ============================================================

def parse_skills_md(md_text: str) -> Dict[str, Skill]:
    """
  Parse un fichier markdown de compétences et retourne un dictionnaire de Skills.
  Format attendu:

  ## **Nom de la compétence**
  - **Catégorie:** Type de compétence
  - **Coût MP:** X MP
  - **Condition:** Condition d'utilisation
  - **Description:** Description détaillée
  """
    skills: Dict[str, Skill] = {}

    current_palier: Optional[str] = None
    cur_skill: Optional[Skill] = None
    cur_key: Optional[str] = None

    for raw in md_text.splitlines():
        line = raw.rstrip("\n")

        # Détection du palier
        m_pal = _RE_PALIER.match(line)
        if m_pal:
            current_palier = f"Palier {int(m_pal.group('pal'))}"
            continue

        # Détection d'une nouvelle compétence
        m_skill = _RE_SKILL_HEADER.match(line)
        if m_skill:
            # Si on a déjà une compétence en cours, on la sauvegarde
            if cur_skill is not None and cur_key is not None:
                skills[cur_key] = cur_skill

            name = _strip_md(m_skill.group("name"))
            cur_skill = Skill(
                name=name,
                category=None,
                description=None,
                cost_mp=None,
                condition=None,
                palier=current_palier
            )
            cur_key = _safe_key(name, skills)
            continue

        if cur_skill is None:
            continue

        # Extraction des attributs de la compétence
        m_cat = _RE_SKILL_CATEGORY.match(line)
        if m_cat:
            cur_skill.category = _strip_md(m_cat.group("cat"))
            continue

        m_cost = _RE_SKILL_COST.match(line)
        if m_cost:
            cur_skill.cost_mp = _strip_md(m_cost.group("cost"))
            continue

        m_cond = _RE_SKILL_CONDITION.match(line)
        if m_cond:
            cur_skill.condition = _strip_md(m_cond.group("cond"))
            continue

        m_desc = _RE_SKILL_DESCRIPTION.match(line)
        if m_desc:
            cur_skill.description = _strip_md(m_desc.group("desc"))
            continue

        # Capture des attributs supplémentaires avec le pattern générique
        m_kv = _RE_KV_ANY.match(line)
        if m_kv:
            k = _strip_md(m_kv.group("k")).lower()
            v = _strip_md(m_kv.group("v"))

            # Si c'est un attribut qu'on n'a pas encore capturé explicitement
            if k == "description" and not cur_skill.description:
                cur_skill.description = v
            elif k == "catégorie" and not cur_skill.category:
                cur_skill.category = v
            elif k in ("coût mp", "cout mp", "coût pm", "cout pm") and not cur_skill.cost_mp:
                cur_skill.cost_mp = v
            elif k == "condition" and not cur_skill.condition:
                cur_skill.condition = v

    # Ne pas oublier la dernière compétence
    if cur_skill is not None and cur_key is not None:
        skills[cur_key] = cur_skill

    return skills


# ============================================================
# API attendue par app.py
# ============================================================

def build_compendium_from_md(bestiaire_path: Path, skill_paths: List[Path]) -> Compendium:
    best_text = Path(bestiaire_path).read_text(encoding="utf-8")
    monsters = parse_monsters_bestiaire(best_text)

    skills: Dict[str, Skill] = {}
    for p in skill_paths:
        p = Path(p)
        if not p.exists():
            continue
        md = p.read_text(encoding="utf-8")
        part = parse_skills_md(md)
        for _, v in part.items():
            key = _safe_key(v.name, skills)
            skills[key] = v

    return Compendium(monsters=monsters, skills=skills)


def build_compendium_from_docs(docs_dir: Path) -> Compendium:
    docs_dir = Path(docs_dir)
    bestiaire = docs_dir / "Bestiaire.md"
    skill_paths = [docs_dir / f"palier{i}.md" for i in range(1, 7)]
    return build_compendium_from_md(bestiaire_path=bestiaire, skill_paths=skill_paths)