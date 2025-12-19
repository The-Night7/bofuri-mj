from typing import Dict, Any

from .models import Entity


def resolve_attack(
  attacker: Entity,
  defender: Entity,
  roll_a: float,
  roll_b: float,
  perce_armure: bool = False,
  vit_scale_div: float = 100.0
) -> Dict[str, Any]:
  """
  Règle fournie :
    si rollA > rollB :
      dégâts = rollA - rollB + STR_A - VIT_B/scale (sauf perce-armure)
    sinon :
      défense = rollB - rollA + VIT_B/scale - STR_A
      si défense > 0 : l'attaquant prend des dégâts
  """
  attacker.ensure_current()
  defender.ensure_current()

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
    out["effects"].append(f"PV {defender.name}: {defender.hp:.2f}/{defender.hp_max:.2f}")
    return out

  # défense réussie (ou égalité)
  defense = (roll_b - roll_a) + vit_term - attacker.STR
  out["raw"]["defense_value"] = float(defense)

  if defense > 0:
    attacker.hp = max(0.0, float(attacker.hp) - float(defense))
    out["effects"].append(f"{defender.name} défend. Contrecoup: {attacker.name} prend {defense:.2f} dégâts.")
    out["effects"].append(f"PV {attacker.name}: {attacker.hp:.2f}/{attacker.hp_max:.2f}")
  else:
    out["effects"].append(f"{defender.name} défend. Aucun dégât en retour (défense ≤ 0).")

  return out
