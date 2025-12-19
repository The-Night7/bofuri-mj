from typing import Dict, Any, Literal
from .models import RuntimeEntity

AttackType = Literal["phys", "magic", "ranged"]

def _attack_stat(attacker: RuntimeEntity, attack_type: AttackType) -> float:
  if attack_type == "phys":
    return float(attacker.STR)
  if attack_type == "magic":
    return float(attacker.INT)
  if attack_type == "ranged":
    return float(attacker.DEX)
  raise ValueError(f"Unknown attack_type: {attack_type}")

def resolve_attack(
  attacker: RuntimeEntity,
  defender: RuntimeEntity,
  roll_a: float,
  roll_b: float,
  attack_type: AttackType = "phys",
  perce_armure: bool = False,
  vit_scale_div: float = 100.0
) -> Dict[str, Any]:
  vit_term = defender.VIT / float(vit_scale_div)

  out: Dict[str, Any] = {
    "hit": False,
    "roll_a": float(roll_a),
    "roll_b": float(roll_b),
    "attack_type": attack_type,
    "perce_armure": bool(perce_armure),
    "vit_scale_div": float(vit_scale_div),
    "raw": {},
    "effects": [],
  }

  atk = _attack_stat(attacker, attack_type)
  out["atk_stat"] = atk

  if roll_a > roll_b:
    out["hit"] = True

    dmg = (roll_a - roll_b) + atk
    if not perce_armure:
      dmg -= vit_term
    dmg = max(0.0, float(dmg))

    defender.hp = max(0.0, float(defender.hp) - dmg)

    out["raw"]["damage"] = dmg
    out["effects"].append(f"{attacker.name} touche {defender.name} et inflige {dmg:.2f} dégâts.")
    out["effects"].append(f"PV {defender.name}: {defender.hp:.2f}/{defender.hp_max:.2f}")
    return out

  defense = (roll_b - roll_a) + vit_term - atk
  out["raw"]["defense_value"] = float(defense)

  if defense > 0:
    attacker.hp = max(0.0, float(attacker.hp) - float(defense))
    out["effects"].append(f"{defender.name} défend. Contrecoup: {attacker.name} prend {defense:.2f} dégâts.")
    out["effects"].append(f"PV {attacker.name}: {attacker.hp:.2f}/{attacker.hp_max:.2f}")
  else:
    out["effects"].append(f"{defender.name} défend. Aucun dégât en retour (défense ≤ 0).")

  return out
