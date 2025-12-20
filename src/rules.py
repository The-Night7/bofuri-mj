from typing import Dict, Any, Literal, Optional
from .models import RuntimeEntity

AttackType = Literal["phys", "magic", "ranged"]


def _attack_stat(attacker: RuntimeEntity, attack_type: AttackType) -> float:
    """Détermine la statistique d'attaque en fonction du type d'attaque"""
    if attack_type == "phys":
        return float(attacker.STR)
    if attack_type == "magic":
        return float(attacker.INT)
    if attack_type == "ranged":
        return float(attacker.DEX)
    raise ValueError(f"Unknown attack_type: {attack_type}")


def _defense_stat(defender: RuntimeEntity, attack_type: AttackType) -> float:
    """Détermine la statistique de défense en fonction du type d'attaque"""
    # VIT est toujours utilisée comme base, mais on peut ajouter des modificateurs
    defense = defender.VIT

    # Bonus de défense selon le type d'attaque
    if attack_type == "phys":
        # Contre les attaques physiques, STR aide un peu à la défense
        defense += defender.STR * 0.2
    elif attack_type == "magic":
        # Contre les attaques magiques, INT aide un peu à la défense
        defense += defender.INT * 0.2
    elif attack_type == "ranged":
        # Contre les attaques à distance, AGI aide un peu à esquiver
        defense += defender.AGI * 0.2

    return float(defense)


def resolve_attack(
        attacker: RuntimeEntity,
        defender: RuntimeEntity,
        roll_a: float,
        roll_b: float,
        attack_type: AttackType = "phys",
        perce_armure: bool = False,
        vit_scale_div: float = 100.0
) -> Dict[str, Any]:
    """
  Résout une attaque entre deux entités.

  Parameters:
  - attacker: L'entité qui attaque
  - defender: L'entité qui défend
  - roll_a: Le jet d'attaque
  - roll_b: Le jet de défense
  - attack_type: Le type d'attaque ("phys", "magic", "ranged")
  - perce_armure: Si True, ignore une partie de la défense
  - vit_scale_div: Diviseur pour la VIT (équilibrage)

  Returns:
  - Un dictionnaire contenant les résultats de l'attaque
  """
    # Calcul de la défense en fonction du type d'attaque
    defense_stat = _defense_stat(defender, attack_type)
    vit_term = defense_stat / float(vit_scale_div)

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

    # Stat d'attaque basée sur le type d'attaque
    atk = _attack_stat(attacker, attack_type)
    out["atk_stat"] = atk
    out["defense_stat"] = defense_stat

    # Messages spécifiques au type d'attaque
    attack_desc = {
        "phys": "frappe",
        "magic": "lance un sort sur",
        "ranged": "tire sur"
    }.get(attack_type, "attaque")

    # Si l'attaquant réussit son jet
    if roll_a > roll_b:
        out["hit"] = True

        # Calcul des dégâts de base
        dmg = (roll_a - roll_b) + atk

        # Modificateurs de dégâts selon le type d'attaque
        if attack_type == "phys":
            # Les attaques physiques sont plus constantes
            dmg = dmg * 1.0
        elif attack_type == "magic":
            # Les attaques magiques sont plus variables (plus fortes ou plus faibles)
            dmg = dmg * (1.2 if roll_a > 15 else 0.9)  # Bonus si bon jet, malus sinon
        elif attack_type == "ranged":
            # Les attaques à distance sont précises mais moins puissantes
            dmg = dmg * 0.95

        # Application de la défense
        if not perce_armure:
            dmg -= vit_term
        else:
            # Même avec perce-armure, on garde une partie de la défense
            dmg -= vit_term * 0.3

        dmg = max(0.0, float(dmg))

        # Application des dégâts
        defender.hp = max(0.0, float(defender.hp) - dmg)

        out["raw"]["damage"] = dmg
        out["effects"].append(f"{attacker.name} {attack_desc} {defender.name} et inflige {dmg:.2f} dégâts.")
        out["effects"].append(f"PV {defender.name}: {defender.hp:.2f}/{defender.hp_max:.2f}")
        return out

    # Si le défenseur réussit sa défense
    defense_power = (roll_b - roll_a) + vit_term - atk
    out["raw"]["defense_value"] = float(defense_power)

    # Contrecoup basé sur le type d'attaque
    if defense_power > 0:
        # Le contrecoup est différent selon le type d'attaque
        if attack_type == "phys":
            # Contrecoup plus fort contre les attaques physiques
            contrecoup = defense_power * 1.0
        elif attack_type == "magic":
            # Contrecoup réduit contre la magie (réflexion de sort partielle)
            contrecoup = defense_power * 0.7
        elif attack_type == "ranged":
            # Contrecoup faible contre les attaques à distance
            contrecoup = defense_power * 0.5

        attacker.hp = max(0.0, float(attacker.hp) - contrecoup)

        # Messages spécifiques selon le type d'attaque
        if attack_type == "phys":
            out["effects"].append(
                f"{defender.name} contre l'attaque. {attacker.name} prend {contrecoup:.2f} dégâts de contrecoup.")
        elif attack_type == "magic":
            out["effects"].append(
                f"{defender.name} résiste au sort. {attacker.name} subit {contrecoup:.2f} dégâts de réflexion magique.")
        elif attack_type == "ranged":
            out["effects"].append(f"{defender.name} esquive et riposte. {attacker.name} prend {contrecoup:.2f} dégâts.")

        out["effects"].append(f"PV {attacker.name}: {attacker.hp:.2f}/{attacker.hp_max:.2f}")
    else:
        # Pas de contrecoup, mais défense réussie
        if attack_type == "phys":
            out["effects"].append(f"{defender.name} bloque l'attaque de {attacker.name}. Aucun dégât en retour.")
        elif attack_type == "magic":
            out["effects"].append(f"{defender.name} dissipe le sort de {attacker.name}. Aucun dégât en retour.")
        elif attack_type == "ranged":
            out["effects"].append(f"{defender.name} évite le tir de {attacker.name}. Aucun dégât en retour.")

    return out