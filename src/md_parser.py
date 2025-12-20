import re
from typing import Dict, List, Optional, Tuple, Any, Set
from pathlib import Path

from .models import Monster, MonsterVariant, Skill, Compendium

# ============================================================
# Regex patterns pour le parsing
# ============================================================

# Headers et sections
_RE_PALIER = re.compile(r"^#+\s+.*PALIER\s+(?P<pal>\d+)")
_RE_MONSTER_HEADER = re.compile(r"^###\s+(?P<name>.*?)(?:\s+\(|\s*$)")
_RE_SKILL_HEADER = re.compile(r"^###\s+(?P<name>.*?)(?:\s+\(|\s*$)")
_RE_SKILL_CATEGORY_HEADER = re.compile(r"^##\s+(?P<category>.*?)(?:\s+\(|\s*$)")

# Attributs des monstres
_RE_LEVEL_RANGE = re.compile(r".*\((?:Lvl|Niveau)\s+(?P<range>[\d\-]+).*\)")
_RE_LEVEL_SPEC = re.compile(r"^(?:\*\*)?(?:Niveau|Level)\s+(?P<level>\d+)(?:\*\*)?:")
_RE_RARITY = re.compile(r".*\(.*(?P<rarity>Élite|Elite|Boss|Rare|Event).*\)")
_RE_HP_MP = re.compile(r"^\s*-\s+\*\*(?P<k>HP|MP):\*\*\s+(?P<v>[\d\.]+(?:/[\d\.]+)?)")
_RE_STAT = re.compile(r"^\s*-\s+\*\*(?P<k>STR|AGI|INT|DEX|VIT):\*\*\s+(?P<v>[\d\.]+)")
_RE_BASE_ATK = re.compile(r"^\s*-\s+\*\*(?:Attaque de base|Base Attack):\*\*\s+(?P<v>.*)")
_RE_DROP = re.compile(r"^\s*-\s+\*\*(?:Drop|Drops?):\*\*\s+(?P<v>.*)")
_RE_ZONE = re.compile(r"^\s*-\s+\*\*Zone:\*\*\s+(?P<v>.*)")
_RE_SKILLS = re.compile(r"^\s*-\s+\*\*(?:Compétences?|Competences?|Skills?):\*\*\s*$")
_RE_SKILL_ITEM = re.compile(r"^\s*-\s+(?:\*\*)?(?P<k>[^:]+)(?:\*\*)?\s*:\s*(?P<v>.*)")

# Attributs des compétences
_RE_SKILL_DESCRIPTION = re.compile(r"^\s*-\s+\*\*(?:Description):\*\*\s+(?P<desc>.*)")
_RE_SKILL_COST = re.compile(r"^\s*-\s+\*\*(?:Coût|Cout|Cost)(?:\s+(?:MP|PM|Mana))?\*\*:\s+(?P<cost>.*)")
_RE_SKILL_CONDITION = re.compile(r"^\s*-\s+\*\*(?:Condition):\*\*\s+(?P<cond>.*)")
_RE_SKILL_INCANTATION = re.compile(r"^\s*-\s+\*\*(?:Incantation):\*\*\s+(?P<incant>.*)")

# Pattern générique pour capturer les paires clé-valeur
_RE_KV_ANY = re.compile(r"^\s*-\s+\*\*(?P<k>[^:]+):\*\*\s+(?P<v>.*)")


# ============================================================
# Helpers
# ============================================================

def _strip_md(text: str) -> str:
    """Retire les marqueurs markdown du texte."""
    return re.sub(r"\*\*|\*|__|\^|~|`", "", text.strip())


def _as_float(text: Optional[str]) -> Optional[float]:
    """Convertit un texte en float, retourne None si impossible."""
    if not text:
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def _safe_key(name: str, existing: Dict) -> str:
    """Génère une clé sûre pour un dictionnaire, en évitant les doublons."""
    base = re.sub(r"[^\w\d]+", "_", name.lower()).strip("_")
    key = base
    counter = 1
    while key in existing:
        key = f"{base}_{counter}"
        counter += 1
    return key


# ============================================================
# Bestiaire - Implémentation du parseur de monstres
# ============================================================

def parse_monsters_bestiaire(md_text: str) -> Dict[str, Monster]:
    """
  Parse un fichier markdown de bestiaire et retourne un dictionnaire de Monster.
  Format attendu:

  ### Nom du monstre (Lvl X-Y / Lvl Z Elite)

  **Niveau X:**
  - **HP:** 100/100
  - **MP:** 50/50
  - **STR:** 10
  - etc.
  """
    monsters: Dict[str, Monster] = {}

    current_palier: Optional[str] = None

    cur_monster_name: Optional[str] = None
    cur_level_range: Optional[str] = None
    cur_rarity: Optional[str] = None
    cur_zone: Optional[str] = None
    cur_drops: List[str] = []
    cur_abilities: List[str] = []

    cur_level: Optional[int] = None
    cur_hp_max: Optional[float] = None
    cur_mp_max: Optional[float] = None
    cur_stats: Dict[str, float] = {}
    cur_base_attack: Optional[str] = None
    cur_extra: Dict[str, str] = {}

    cur_variants: Dict[int, MonsterVariant] = {}

    in_skills_section = False
    skill_buffer = []

    def _ensure_variant_level():
        nonlocal cur_level, cur_hp_max, cur_mp_max, cur_stats, cur_base_attack, cur_extra, cur_variants

        if cur_level is not None and cur_hp_max is not None and cur_mp_max is not None and cur_stats:
            variant = MonsterVariant(
                level=cur_level,
                hp_max=cur_hp_max,
                mp_max=cur_mp_max,
                STR=cur_stats.get("STR", 0),
                AGI=cur_stats.get("AGI", 0),
                INT=cur_stats.get("INT", 0),
                DEX=cur_stats.get("DEX", 0),
                VIT=cur_stats.get("VIT", 0),
                base_attack=_as_float(cur_base_attack),
                extra=cur_extra.copy() if cur_extra else None,
            )
            cur_variants[cur_level] = variant

            # Reset pour la prochaine variante
            cur_level = None
            cur_hp_max = None
            cur_mp_max = None
            cur_stats = {}
            cur_base_attack = None
            cur_extra = {}

    def flush_monster():
        nonlocal cur_monster_name, cur_level_range, cur_rarity, cur_zone, cur_drops, cur_abilities
        nonlocal cur_variants, in_skills_section, skill_buffer

        _ensure_variant_level()

        if cur_monster_name:
            # Traitement des compétences accumulées dans le buffer
            if skill_buffer and not cur_abilities:
                cur_abilities = [s.strip() for s in skill_buffer if s.strip()]

            monster = Monster(
                name=cur_monster_name,
                palier=current_palier,
                level_range=cur_level_range,
                rarity=cur_rarity,
                zone=cur_zone,
                drops=cur_drops if cur_drops else None,
                abilities=cur_abilities if cur_abilities else None,
                variants=cur_variants,
            )

            key = _safe_key(cur_monster_name, monsters)
            monsters[key] = monster

        # Reset pour le prochain monstre
        cur_monster_name = None
        cur_level_range = None
        cur_rarity = None
        cur_zone = None
        cur_drops = []
        cur_abilities = []
        cur_variants = {}
        in_skills_section = False
        skill_buffer = []

    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Détection du palier
        m_pal = _RE_PALIER.match(line)
        if m_pal:
            flush_monster()
            current_palier = f"Palier {int(m_pal.group('pal'))}"
            i += 1
            continue

        # Détection d'un nouveau monstre
        m_monster = _RE_MONSTER_HEADER.match(line)
        if m_monster:
            flush_monster()
            cur_monster_name = _strip_md(m_monster.group("name"))

            # Extraction du niveau et rareté depuis l'en-tête
            m_lvl_range = _RE_LEVEL_RANGE.match(line)
            if m_lvl_range:
                cur_level_range = m_lvl_range.group("range")

            m_rarity = _RE_RARITY.match(line)
            if m_rarity:
                cur_rarity = m_rarity.group("rarity")
            elif "👑" in line:
                cur_rarity = "Boss"

            i += 1
            continue

        # Si on n'a pas encore de nom de monstre, on vérifie s'il y a des stats directes
        # (cas du premier monstre sans en-tête)
        if not cur_monster_name and ((_RE_HP_MP.match(line) or _RE_STAT.match(line)) and i > 0):
            # On cherche un nom dans les lignes précédentes
            for j in range(i - 1, max(0, i - 5), -1):
                if lines[j].strip() and not lines[j].startswith("-") and not lines[j].startswith("#"):
                    cur_monster_name = _strip_md(lines[j])
                    break

            # Si toujours pas de nom, on utilise un placeholder
            if not cur_monster_name:
                cur_monster_name = "Monstre sans nom"

        # Détection du niveau de la variante
        m_lvl = _RE_LEVEL_SPEC.match(line)
        if m_lvl:
            _ensure_variant_level()  # Finaliser la variante précédente si elle existe
            cur_level = int(m_lvl.group("level"))
            i += 1
            continue

        # Extraction des attributs du monstre
        m_drop = _RE_DROP.match(line)
        if m_drop:
            drops_text = _strip_md(m_drop.group("v"))
            cur_drops = [d.strip() for d in drops_text.split(",")]
            i += 1
            continue

        m_zone = _RE_ZONE.match(line)
        if m_zone:
            cur_zone = _strip_md(m_zone.group("v"))
            i += 1
            continue

        # Début de la section compétences
        m_skills = _RE_SKILLS.match(line)
        if m_skills:
            in_skills_section = True
            i += 1
            # Capture les lignes suivantes comme compétences jusqu'à un pattern qui ne correspond plus
            while i < len(lines) and lines[i].strip().startswith("-"):
                skill_buffer.append(_strip_md(lines[i]))
                i += 1
            continue

        # Extraction des stats HP/MP
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
            i += 1
            continue

        # Extraction des autres stats
        m_stat = _RE_STAT.match(line)
        if m_stat:
            k = m_stat.group("k").upper()
            val = _as_float(m_stat.group("v"))
            if val is not None:
                cur_stats[k] = val
            i += 1
            continue

        # Extraction de l'attaque de base
        m_ba = _RE_BASE_ATK.match(line)
        if m_ba:
            cur_base_attack = _strip_md(m_ba.group("v"))
            i += 1
            continue

        # Extraction des compétences individuelles
        m_skill_item = _RE_SKILL_ITEM.match(line)
        if m_skill_item and not in_skills_section:
            skill_name = _strip_md(m_skill_item.group("k"))
            skill_desc = _strip_md(m_skill_item.group("v"))

            if skill_name.lower() not in ("hp", "mp", "str", "agi", "int", "dex", "vit",
                                          "attaque de base", "drop", "zone", "compétences", "competences"):
                if not cur_abilities:
                    cur_abilities = []
                cur_abilities.append(f"{skill_name}: {skill_desc}")
            i += 1
            continue

        # Extraction d'autres attributs avec le pattern générique
        m_kv = _RE_KV_ANY.match(line)
        if m_kv:
            k = _strip_md(m_kv.group("k"))
            v = _strip_md(m_kv.group("v"))

            # Ignorer les attributs déjà traités
            if k.lower() in ("hp", "mp", "str", "agi", "int", "dex", "vit", "attaque de base",
                             "drop", "zone", "compétences", "competences"):
                i += 1
                continue

            cur_extra[k] = v
            i += 1
            continue

        # Si on trouve un séparateur, c'est la fin du monstre actuel
        if line.strip() == "---":
            flush_monster()
            i += 1
            continue

        i += 1

    # Ne pas oublier le dernier monstre
    flush_monster()
    return monsters


# ============================================================
# Skills - Implémentation du parseur de compétences
# ============================================================

def parse_skills_md(md_text: str) -> Dict[str, Skill]:
    """
Parse un fichier markdown de compétences et retourne un dictionnaire de Skills.
Format attendu:

### Nom de la compétence
- **Description:** Description détaillée
- **Coût MP:** X PM
- **Condition:** Condition d'utilisation
"""
    skills: Dict[str, Skill] = {}

    current_palier: Optional[str] = None
    current_category: Optional[str] = None

    cur_skill_name: Optional[str] = None
    cur_description: Optional[str] = None
    cur_cost: Optional[str] = None
    cur_condition: Optional[str] = None
    cur_extra: Dict[str, str] = {}

    def flush_skill():
        nonlocal cur_skill_name, cur_description, cur_cost, cur_condition, cur_extra

        if cur_skill_name:
            skill = Skill(
                name=cur_skill_name,
                category=current_category,
                description=cur_description,
                cost_mp=cur_cost,
                condition=cur_condition,
                palier=current_palier
            )

            # Ajouter des informations supplémentaires si nécessaire
            if cur_extra:
                for k, v in cur_extra.items():
                    if not hasattr(skill, k.lower()) or getattr(skill, k.lower()) is None:
                        setattr(skill, k.lower(), v)

            key = _safe_key(cur_skill_name, skills)
            skills[key] = skill

        # Réinitialiser pour la prochaine compétence
        cur_skill_name = None
        cur_description = None
        cur_cost = None
        cur_condition = None
        cur_extra = {}

    for raw in md_text.splitlines():
        line = raw.rstrip("\n")

        # Détection du palier
        m_pal = _RE_PALIER.match(line)
        if m_pal:
            current_palier = f"Palier {int(m_pal.group('pal'))}"
            continue

        # Détection d'une catégorie de compétences
        m_cat = _RE_SKILL_CATEGORY_HEADER.match(line)
        if m_cat:
            flush_skill()  # Finaliser la compétence en cours si elle existe
            category_text = m_cat.group('category')
            current_category = _strip_md(category_text)
            continue

        # Détection d'une nouvelle compétence
        m_skill = _RE_SKILL_HEADER.match(line)
        if m_skill:
            flush_skill()  # Finaliser la compétence précédente
            cur_skill_name = _strip_md(m_skill.group("name"))
            continue

        # Si on n'a pas encore de nom de compétence, on continue
        if not cur_skill_name:
            continue

        # Extraction des attributs de la compétence
        m_desc = _RE_SKILL_DESCRIPTION.match(line)
        if m_desc:
            cur_description = _strip_md(m_desc.group("desc"))
            continue

        m_cost = _RE_SKILL_COST.match(line)
        if m_cost:
            cur_cost = _strip_md(m_cost.group("cost"))
            continue

        m_cond = _RE_SKILL_CONDITION.match(line)
        if m_cond:
            cur_condition = _strip_md(m_cond.group("cond"))
            continue

        m_incant = _RE_SKILL_INCANTATION.match(line)
        if m_incant:
            cur_extra["incantation"] = _strip_md(m_incant.group("incant"))
            continue

        # Capture des attributs supplémentaires avec le pattern générique
        m_kv = _RE_KV_ANY.match(line)
        if m_kv:
            k = _strip_md(m_kv.group("k")).lower()
            v = _strip_md(m_kv.group("v"))

            if k == "description" and not cur_description:
                cur_description = v
            elif k in ("coût mp", "cout mp", "coût pm", "cout pm") and not cur_cost:
                cur_cost = v
            elif k == "condition" and not cur_condition:
                cur_condition = v
            else:
                cur_extra[k] = v

        # Si on rencontre une ligne séparatrice (---), on considère que c'est la fin de la compétence actuelle
        if line.strip() == "---":
            flush_skill()

    # Ne pas oublier la dernière compétence
    flush_skill()

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
        for k, v in part.items():
            key = _safe_key(v.name, skills)
            skills[key] = v

    return Compendium(monsters=monsters, skills=skills)


def build_compendium_from_docs(docs_dir: Path) -> Compendium:
    docs_dir = Path(docs_dir)
    bestiaire = docs_dir / "Bestiaire.md"
    skill_paths = [docs_dir / f"palier{i}.md" for i in range(1, 7)]
    return build_compendium_from_md(bestiaire_path=bestiaire, skill_paths=skill_paths)