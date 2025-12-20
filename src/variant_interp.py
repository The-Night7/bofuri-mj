"""
Utilitaire: obtenir un "MonsterVariant" au niveau lvl même si le compendium
ne stocke que des stats min/max (ou quelques paliers).

- Interpolation linéaire entre deux variants encadrants
- Arrondi des stats (round) pendant l'adaptation
- Clamp si lvl hors bornes
- Retourne un dict compatible (clé->valeurs)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple, List


def _lerp(a: float, b: float, t: float) -> float:
  return a + (b - a) * t


def _round_stat(x: float) -> float:
  # <- Modifie ici si tu veux plutôt int(x), math.ceil, etc.
  return float(round(x))


def _coerce_level_key(k: Any) -> Optional[int]:
  try:
    return int(k)
  except Exception:
    return None


def _extract_stats_from_abilities(abilities: List[str]) -> Dict[str, float]:
  """
  Extrait les statistiques à partir d'une liste de capacités au format texte
  """
  stats = {
    "hp_max": 0.0,
    "mp_max": 0.0,
    "STR": 0.0,
    "AGI": 0.0,
    "INT": 0.0,
    "DEX": 0.0,
    "VIT": 0.0,
    "base_attack": 0.0
  }

  for ability in abilities:
    # HP: 15/15
    hp_match = re.match(r"HP\s*:\s*(\d+)(?:/\d+)?", ability)
    if hp_match:
      stats["hp_max"] = float(hp_match.group(1))
      continue

    # MP: 10/10
    mp_match = re.match(r"MP\s*:\s*(\d+)(?:/\d+)?", ability)
    if mp_match:
      stats["mp_max"] = float(mp_match.group(1))
      continue

    # STR: 4
    stat_match = re.match(r"(STR|AGI|INT|DEX|VIT)\s*:\s*(\d+)", ability)
    if stat_match:
      stat_name = stat_match.group(1)
      stat_value = float(stat_match.group(2))
      stats[stat_name] = stat_value
      continue

    # Attaque de base: 5
    atk_match = re.match(r"Attaque\s+de\s+base\s*:\s*(\d+)", ability)
    if atk_match:
      stats["base_attack"] = float(atk_match.group(1))
      continue

  return stats


def _extract_variant_fields(v: Any) -> Dict[str, float]:
  """
  Accepte:
    - un dict {"hp_max": 12, ...}
    - un dataclass-like avec attributs .hp_max, .STR, etc.
  Retourne un dict normalisé (float).
  """
  if isinstance(v, dict):
    get = v.get
  else:
    get = lambda key, default=None: getattr(v, key, default)

  # Vérifier si les stats sont à 0 et s'il y a des abilities
  extra = _extract_extra(v)
  abilities = extra.get("abilities", [])

  # Si toutes les stats principales sont à 0 et qu'il y a des abilities, essayer de les extraire
  base_stats = {
    "hp_max": float(get("hp_max", 0.0) or 0.0),
    "mp_max": float(get("mp_max", 0.0) or 0.0),
    "STR": float(get("STR", 0.0) or 0.0),
    "AGI": float(get("AGI", 0.0) or 0.0),
    "INT": float(get("INT", 0.0) or 0.0),
    "DEX": float(get("DEX", 0.0) or 0.0),
    "VIT": float(get("VIT", 0.0) or 0.0),
    # base_attack peut être None dans tes données
    "base_attack": float(get("base_attack", 0.0) or 0.0),
  }

  # Si toutes les stats principales sont à 0 et qu'il y a des abilities
  if all(v == 0.0 for k, v in base_stats.items() if k != "base_attack") and abilities:
    ability_stats = _extract_stats_from_abilities(abilities)
    # Mettre à jour les stats avec celles extraites des abilities
    for k, v in ability_stats.items():
      if v > 0.0:  # Ne remplacer que si la valeur extraite est > 0
        base_stats[k] = v

  return base_stats


def _extract_extra(v: Any) -> Dict[str, Any]:
  if isinstance(v, dict):
    extra = v.get("extra") or {}
  else:
    extra = getattr(v, "extra", None) or {}
  if not isinstance(extra, dict):
    return {}
  return dict(extra)


def _bounds_for_level(levels: list[int], lvl: int) -> Tuple[int, int]:
  """
  Renvoie (l0, l1) tels que:
  - si lvl est dans levels: (lvl, lvl)
  - sinon l0 < lvl < l1 et l0/l1 sont les plus proches bornes
  """
  if lvl in levels:
    return (lvl, lvl)
  # clamp géré ailleurs, ici on suppose levels triés et lvl dans (min,max)
  l0 = max(L for L in levels if L < lvl)
  l1 = min(L for L in levels if L > lvl)
  return (l0, l1)


def _extract_level_from_range(level_range: Optional[str]) -> int:
  """Extrait un niveau à partir d'une chaîne de plage de niveaux"""
  if not level_range:
    return 1

  # Cas "1-5" -> prend la moyenne
  if "-" in level_range:
    try:
      min_lvl, max_lvl = map(int, level_range.split("-"))
      return (min_lvl + max_lvl) // 2
    except:
      pass

  # Essaie d'extraire un nombre simple
  match = re.search(r'\d+', level_range)
  if match:
    return int(match.group(0))

  return 1  # Niveau par défaut


def interpolated_variant(monster: Any, lvl: int) -> Optional[Dict[str, Any]]:
  """
  monster.variants doit être un dict dont les clés sont des niveaux (int ou str).
  Si monster n'a pas de variants mais a des abilities, extrait les stats des abilities.

  Retour:
    dict:
      {
        "level": lvl,
        "hp_max": ...,
        "mp_max": ...,
        "STR": ...,
        "AGI": ...,
        "INT": ...,
        "DEX": ...,
        "VIT": ...,
        "base_attack": ...,
        "extra": {...}
      }
    ou None si pas de variants et pas d'abilities
  """
  variants = getattr(monster, "variants", None)

  # Si pas de variants mais des abilities, on construit une variante à partir des abilities
  if not variants or not variants:
    abilities = getattr(monster, "abilities", None)
    if abilities:
      # Extraire les stats des abilities
      stats = _extract_stats_from_abilities(abilities)

      # Déterminer le niveau à partir du level_range si disponible
      level_range = getattr(monster, "level_range", None)
      monster_level = _extract_level_from_range(level_range)

      # Si le niveau demandé est différent, on ajuste légèrement les stats
      level_factor = lvl / monster_level if monster_level > 0 else 1

      # Construire une variante avec les stats extraites
      return {
        "level": lvl,
        "hp_max": _round_stat(stats["hp_max"] * level_factor),
        "mp_max": _round_stat(stats["mp_max"] * level_factor),
        "STR": _round_stat(stats["STR"] * level_factor),
        "AGI": _round_stat(stats["AGI"] * level_factor),
        "INT": _round_stat(stats["INT"] * level_factor),
        "DEX": _round_stat(stats["DEX"] * level_factor),
        "VIT": _round_stat(stats["VIT"] * level_factor),
        "base_attack": stats["base_attack"] * level_factor,
        "extra": {"abilities": abilities}
      }
    return None

  # normaliser niveaux
  level_map: Dict[int, Any] = {}
  for k, v in variants.items():
    ik = _coerce_level_key(k)
    if ik is None:
      continue
    level_map[ik] = v

  if not level_map:
    return None

  levels = sorted(level_map.keys())

  # clamp hors bornes
  if lvl <= levels[0]:
    v = level_map[levels[0]]
    data = _extract_variant_fields(v)
    return {
      "level": levels[0],
      **{k: _round_stat(val) for k, val in data.items() if k != "base_attack"},
      "base_attack": data["base_attack"],  # souvent mieux de ne pas arrondir si c'est déjà "propre"
      "extra": _extract_extra(v),
    }

  if lvl >= levels[-1]:
    v = level_map[levels[-1]]
    data = _extract_variant_fields(v)
    return {
      "level": levels[-1],
      **{k: _round_stat(val) for k, val in data.items() if k != "base_attack"},
      "base_attack": data["base_attack"],
      "extra": _extract_extra(v),
    }

  l0, l1 = _bounds_for_level(levels, lvl)
  if l0 == l1:
    v = level_map[l0]
    data = _extract_variant_fields(v)
    return {
      "level": lvl,
      **{k: _round_stat(val) for k, val in data.items() if k != "base_attack"},
      "base_attack": data["base_attack"],
      "extra": _extract_extra(v),
    }

  v0 = level_map[l0]
  v1 = level_map[l1]

  d0 = _extract_variant_fields(v0)
  d1 = _extract_variant_fields(v1)

  t = (lvl - l0) / (l1 - l0)

  out: Dict[str, Any] = {"level": lvl}
  for key in ["hp_max", "mp_max", "STR", "AGI", "INT", "DEX", "VIT", "base_attack"]:
    val = _lerp(d0[key], d1[key], t)
    # arrondir toutes les stats "entiers"
    if key == "base_attack":
      out[key] = val
    else:
      out[key] = _round_stat(val)

  # "extra": stratégie simple
  # - si v0/v1 ont extra, tu peux choisir celui de la borne la plus proche
  extra0 = _extract_extra(v0)
  extra1 = _extract_extra(v1)
  out["extra"] = extra0 if t < 0.5 else extra1

  return out