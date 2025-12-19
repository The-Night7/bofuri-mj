"""
Utilitaire: obtenir un "MonsterVariant" au niveau lvl même si le compendium
ne stocke que des stats min/max (ou quelques paliers).

- Interpolation linéaire entre deux variants encadrants
- Arrondi des stats (round) pendant l'adaptation
- Clamp si lvl hors bornes
- Retourne un dict compatible (clé->valeurs)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


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

  return {
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


def interpolated_variant(monster: Any, lvl: int) -> Optional[Dict[str, Any]]:
  """
  monster.variants doit être un dict dont les clés sont des niveaux (int ou str).

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
    ou None si pas de variants
  """
  variants = getattr(monster, "variants", None)
  if not variants:
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