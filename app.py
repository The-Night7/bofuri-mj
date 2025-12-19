import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

import streamlit as st


# -----------------------------
# Data model
# -----------------------------
@dataclass
class Entity:
  name: str
  kind: str  # "PJ" | "Mob" | "Boss"
  level: int
  hp_max: float
  mp_max: float
  STR: float
  AGI: float
  INT: float
  DEX: float
  VIT: float
  hp: Optional[float] = None
  mp: Optional[float] = None

  def ensure_current(self):
    if self.hp is None:
      self.hp = float(self.hp_max)
    if self.mp is None:
      self.mp = float(self.mp_max)

  @staticmethod
  def from_dict(d: Dict[str, Any]) -> "Entity":
    return Entity(
      name=d["name"],
      kind=d.get("kind", "PJ"),
      level=int(d.get("level", 1)),
      hp_max=float(d.get("hp_max", 0)),
      mp_max=float(d.get("mp_max", 0)),
      STR=float(d.get("STR", 0)),
      AGI=float(d.get("AGI", 0)),
      INT=float(d.get("INT", 0)),
      DEX=float(d.get("DEX", 0)),
      VIT=float(d.get("VIT", 0)),
      hp=float(d["hp"]) if "hp" in d else None,
      mp=float(d["mp"]) if "mp" in d else None,
    )

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


# -----------------------------
# Storage helpers
# -----------------------------
DATA_DIR = Path("data")
ENTITIES_PATH = DATA_DIR / "entities.json"


def default_entities() -> Dict[str, Any]:
  # Exemple minimal. Tu peux remplacer/compléter avec ton bestiaire.
  return {
    "entities": [
      {
        "name": "PJ — Exemple Guerrier",
        "kind": "PJ",
        "level": 10,
        "hp_max": 300,
        "mp_max": 50,
        "STR": 35,
        "AGI": 12,
        "INT": 5,
        "DEX": 10,
        "VIT": 25
      },
      {
        "name": "Lapin végétal (Lvl 1)",
        "kind": "Mob",
        "level": 1,
        "hp_max": 10,
        "mp_max": 5,
        "STR": 3,
        "AGI": 8,
        "INT": 2,
        "DEX": 5,
        "VIT": 2
      },
      {
        "name": "BEE ME ME BEE (Lvl 10)",
        "kind": "Mob",
        "level": 10,
        "hp_max": 50,
        "mp_max": 30,
        "STR": 15,
        "AGI": 25,
        "INT": 8,
        "DEX": 20,
        "VIT": 10
      },
      {
        "name": "Hydre au poison (Lvl 15)",
        "kind": "Boss",
        "level": 15,
        "hp_max": 1500,
        "mp_max": 200,
        "STR": 60,
        "AGI": 20,
        "INT": 45,
        "DEX": 30,
        "VIT": 80
      }
    ]
  }


def load_entities() -> List[Entity]:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  if not ENTITIES_PATH.exists():
    ENTITIES_PATH.write_text(json.dumps(default_entities(), ensure_ascii=False, indent=2), encoding="utf-8")

  raw = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
  entities = [Entity.from_dict(e) for e in raw.get("entities", [])]
  for e in entities:
    e.ensure_current()
  return entities


def save_entities(entities: List[Entity]) -> None:
  payload = {"entities": [e.to_dict() for e in entities]}
  ENTITIES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_entity(entities: List[Entity], name: str) -> Optional[Entity]:
  for e in entities:
    if e.name == name:
      return e
  return None


# -----------------------------
# Combat rule
# -----------------------------
def resolve_attack(
  attacker: Entity,
  defender: Entity,
  roll_a: float,
  roll_b: float,
  perce_armure: bool = False,
  vit_scale_div: float = 100.0
) -> Dict[str, Any]:
  """
  Règle fournie par l'utilisateur.

  Si rollA > rollB:
    dégâts = rollA - rollB + STR_A - VIT_B/scale (sauf perce-armure)
  Sinon:
    défense = rollB - rollA + VIT_B/scale - STR_A
    si défense > 0: l'attaquant prend défense dégâts
  """
  vit_term = defender.VIT / vit_scale_div

  out = {
    "hit": False,
    "roll_a": roll_a,
    "roll_b": roll_b,
    "perce_armure": perce_armure,
    "vit_scale_div": vit_scale_div,
    "raw": {},
    "effects": [],
  }

  if roll_a > roll_b:
    out["hit"] = True
    dmg = (roll_a - roll_b) + attacker.STR
    if not perce_armure:
      dmg -= vit_term
    dmg = max(0.0, dmg)

    defender.hp = max(0.0, float(defender.hp) - dmg)

    out["raw"]["damage"] = dmg
    out["effects"].append(f"{attacker.name} touche {defender.name} et inflige {dmg:.2f} dégâts.")
    out["effects"].append(f"PV {defender.name}: {defender.hp:.2f}/{defender.hp_max:.2f}")
    return out

  # Défense réussie (ou égalité)
  defense = (roll_b - roll_a) + vit_term - attacker.STR
  out["raw"]["defense_value"] = defense

  if defense > 0:
    attacker.hp = max(0.0, float(attacker.hp) - defense)
    out["effects"].append(
      f"{defender.name} défend. Contrecoup: {attacker.name} prend {defense:.2f} dégâts."
    )
    out["effects"].append(f"PV {attacker.name}: {attacker.hp:.2f}/{attacker.hp_max:.2f}")
  else:
    out["effects"].append(f"{defender.name} défend. Aucun dégât en retour (défense ≤ 0).")

  return out


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Bofuri RP — Assistant MJ", layout="wide")
st.title("Assistant MJ — Bofuri RP (Duel de rolls)")

entities = load_entities()
name_list = [e.name for e in entities]

if "combat_log" not in st.session_state:
  st.session_state.combat_log = []

if "last_result" not in st.session_state:
  st.session_state.last_result = None

col_left, col_right = st.columns([1, 1])

with col_left:
  st.subheader("Sélection des combattants")
  attacker_name = st.selectbox("Attaquant (A)", name_list, index=0)
  defender_name = st.selectbox("Défenseur (B)", name_list, index=min(1, len(name_list)-1))

  attacker = find_entity(entities, attacker_name)
  defender = find_entity(entities, defender_name)

  if attacker is None or defender is None:
    st.error("Entité introuvable (problème de base de données).")
    st.stop()

  if attacker.name == defender.name:
    st.warning("Attaquant et défenseur sont identiques : choisis deux entités différentes.")

  st.markdown("### Stats rapides")
  c1, c2 = st.columns(2)
  with c1:
    st.markdown(f"**A — {attacker.name}**  \nType: {attacker.kind} | Lvl {attacker.level}")
    st.write({"HP": f"{attacker.hp:.2f}/{attacker.hp_max:.2f}", "MP": f"{attacker.mp:.2f}/{attacker.mp_max:.2f}"})
    st.write({"STR": attacker.STR, "VIT": attacker.VIT, "AGI": attacker.AGI, "DEX": attacker.DEX, "INT": attacker.INT})
  with c2:
    st.markdown(f"**B — {defender.name}**  \nType: {defender.kind} | Lvl {defender.level}")
    st.write({"HP": f"{defender.hp:.2f}/{defender.hp_max:.2f}", "MP": f"{defender.mp:.2f}/{defender.mp_max:.2f}"})
    st.write({"STR": defender.STR, "VIT": defender.VIT, "AGI": defender.AGI, "DEX": defender.DEX, "INT": defender.INT})

with col_right:
  st.subheader("Résolution du duel")
  c1, c2, c3 = st.columns([1, 1, 1])

  with c1:
    roll_a = st.number_input("Roll A (x)", min_value=0.0, max_value=100.0, value=10.0, step=1.0)
  with c2:
    roll_b = st.number_input("Roll B (y)", min_value=0.0, max_value=100.0, value=10.0, step=1.0)
  with c3:
    vit_div = st.number_input("Diviseur VIT (VIT/?)", min_value=1.0, max_value=1000.0, value=100.0, step=1.0)

  perce_armure = st.checkbox("Skill: Perce-armure (ignore VIT B dans les dégâts)", value=False)

  cbtn1, cbtn2, cbtn3 = st.columns([1, 1, 1])
  do_resolve = cbtn1.button("Résoudre l'attaque", type="primary")
  do_reset_hp = cbtn2.button("Reset PV/PM (tous)")
  do_save = cbtn3.button("Sauvegarder base (PV/PM inclus)")

  if do_reset_hp:
    for e in entities:
      e.hp = float(e.hp_max)
      e.mp = float(e.mp_max)
    st.success("PV/PM réinitialisés pour toutes les entités.")
    st.rerun()

  if do_resolve:
    if attacker.name == defender.name:
      st.error("Impossible: A et B sont la même entité.")
    else:
      result = resolve_attack(attacker, defender, roll_a, roll_b, perce_armure=perce_armure, vit_scale_div=vit_div)
      st.session_state.last_result = result
      st.session_state.combat_log.extend(result["effects"])

  if do_save:
    save_entities(entities)
    st.success(f"Base sauvegardée dans: {ENTITIES_PATH.as_posix()}")

  st.markdown("### Résultat")
  if st.session_state.last_result is None:
    st.info("Aucun duel résolu pour l’instant.")
  else:
    r = st.session_state.last_result
    st.write({
      "Touché ?": r["hit"],
      "Roll A": r["roll_a"],
      "Roll B": r["roll_b"],
      "Perce-armure": r["perce_armure"],
      "Diviseur VIT": r["vit_scale_div"],
      **r["raw"]
    })
    for line in r["effects"]:
      st.text(line)

  st.markdown("### Log de combat")
  if st.session_state.combat_log:
    st.text("\n".join(st.session_state.combat_log[-40:]))
    if st.button("Vider le log"):
      st.session_state.combat_log = []
      st.rerun()
  else:
    st.caption("Le log apparaîtra ici.")

st.divider()
st.subheader("Éditeur rapide — Ajouter une entité")
with st.expander("Créer un PJ / Mob / Boss"):
  with st.form("create_entity_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
      n = st.text_input("Nom", value="Nouveau Mob")
      kind = st.selectbox("Type", ["PJ", "Mob", "Boss"], index=1)
      lvl = st.number_input("Niveau", min_value=1, max_value=999, value=1, step=1)
    with c2:
      hp_max = st.number_input("HP max", min_value=0.0, value=50.0, step=10.0)
      mp_max = st.number_input("MP max", min_value=0.0, value=10.0, step=5.0)
      STR = st.number_input("STR", min_value=0.0, value=5.0, step=1.0)
    with c3:
      VIT = st.number_input("VIT", min_value=0.0, value=5.0, step=1.0)
      AGI = st.number_input("AGI", min_value=0.0, value=5.0, step=1.0)
      DEX = st.number_input("DEX", min_value=0.0, value=5.0, step=1.0)
      INT = st.number_input("INT", min_value=0.0, value=5.0, step=1.0)

    submitted = st.form_submit_button("Ajouter")
    if submitted:
      ent = Entity(
        name=n, kind=kind, level=int(lvl),
        hp_max=float(hp_max), mp_max=float(mp_max),
        STR=float(STR), AGI=float(AGI), INT=float(INT), DEX=float(DEX), VIT=float(VIT),
        hp=float(hp_max), mp=float(mp_max)
      )
      entities.append(ent)
      save_entities(entities)
      st.success("Entité ajoutée et sauvegardée.")
      st.rerun()

st.caption("Prochaine étape possible: import automatique depuis tes fichiers .md (Bestiaire/Armures/Skills/Objets/XP).")