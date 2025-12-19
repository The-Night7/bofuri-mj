from typing import Dict, Any
from .models import RuntimeEntity


def resolve_attack(
  attacker: RuntimeEntity,
  defender: RuntimeEntity,
  roll_a: float,
  roll_b: float,
  perce_armure: bool = False,
  vit_scale_div: float = 100.0
) -> Dict[str, Any]:
  """
  Règle :
    si x > y :
      dégâts = (x - y) + STR_A - VIT_B/scale (sauf perce-armure)
    sinon :
      défense = (y - x) + VIT_B/scale - STR_A
      si défense > 0 : l'attaquant prend défense dégâts
  """
  vit_term = defender.VIT / float(vit_scale_div)

  out: Dict[str, Any] = {
    "hit": False,
    "roll_a": float(roll_a),
    "roll_b": float(roll_b),
    "perce_armure": bool(perce_armure),
    "vit_scale_div": float(vit_scale_div),
    "raw": {},
    "effects": [],
  }

  if roll_a > roll_b:
    out["hit"] = True
    dmg = (roll_a - roll_b) + attacker.STR
    if not perce_armure:
      dmg -= vit_term
    dmg = max(0.0, float(dmg))

    defender.hp = max(0.0, float(defender.hp) - dmg)

    out["raw"]["damage"] = dmg
    out["effects"].append(f"{attacker.name} touche {defender.name} et inflige {dmg:.2f} dégâts.")

    # Infos bestiaire (si présentes)
    if attacker.base_attack is not None:
      out["effects"].append(f"(Info) Attaque de base {attacker.name}: {attacker.base_attack}")
    if defender.zone:
      out["effects"].append(f"(Info) Zone {defender.name}: {defender.zone}")

    out["effects"].append(f"PV {defender.name}: {defender.hp:.2f}/{defender.hp_max:.2f}")
    return out

  defense = (roll_b - roll_a) + vit_term - attacker.STR
  out["raw"]["defense_value"] = float(defense)

  if defense > 0:
    attacker.hp = max(0.0, float(attacker.hp) - float(defense))
    out["effects"].append(f"{defender.name} défend. Contrecoup: {attacker.name} prend {defense:.2f} dégâts.")
    out["effects"].append(f"PV {attacker.name}: {attacker.hp:.2f}/{attacker.hp_max:.2f}")
  else:
    out["effects"].append(f"{defender.name} défend. Aucun dégât en retour (défense ≤ 0).")

  return out
