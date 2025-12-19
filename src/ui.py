import streamlit as st
from typing import List, Callable

from .models import Entity


def render_entity_panel(entity: Entity, title: str = "") -> None:
  if title:
    st.markdown(f"### {title}")

  st.markdown(f"**{entity.name}**  \nType: {entity.kind} | Lvl {entity.level}")
  st.write({
    "HP": f"{entity.hp:.2f}/{entity.hp_max:.2f}",
    "MP": f"{entity.mp:.2f}/{entity.mp_max:.2f}",
  })
  st.write({
    "STR": entity.STR,
    "VIT": entity.VIT,
    "AGI": entity.AGI,
    "DEX": entity.DEX,
    "INT": entity.INT,
  })


def render_log_panel() -> None:
  st.subheader("Log de combat")
  log = st.session_state.get("combat_log", [])
  if not log:
    st.caption("Le log apparaîtra ici.")
    return

  st.text("\n".join(log[-60:]))

  c1, c2 = st.columns([1, 1])
  if c1.button("Vider le log"):
    st.session_state.combat_log = []
    st.rerun()
  if c2.button("Copier (afficher tout)"):
    st.text("\n".join(log))


def render_create_entity_form(entities: List[Entity], on_save: Callable[[], None]) -> None:
  with st.form("create_entity_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
      name = st.text_input("Nom", value="Nouveau Mob")
      kind = st.selectbox("Type", ["PJ", "Mob", "Boss"], index=1)
      level = st.number_input("Niveau", min_value=1, max_value=999, value=1, step=1)

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
        name=name,
        kind=kind,
        level=int(level),
        hp_max=float(hp_max),
        mp_max=float(mp_max),
        STR=float(STR),
        AGI=float(AGI),
        INT=float(INT),
        DEX=float(DEX),
        VIT=float(VIT),
        hp=float(hp_max),
        mp=float(mp_max),
      )
      entities.append(ent)
      on_save()
      st.success("Entité ajoutée et sauvegardée.")
      st.rerun()


def render_edit_entity_form(entities: List[Entity], on_save: Callable[[], None]) -> None:
  if not entities:
    st.caption("Aucune entité à modifier.")
    return

  names = [e.name for e in entities]
  selected = st.selectbox("Choisir une entité", names, index=0, key="edit_entity_select")
  entity = next(e for e in entities if e.name == selected)

  with st.form("edit_entity_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
      name = st.text_input("Nom", value=entity.name)
      kind = st.selectbox("Type", ["PJ", "Mob", "Boss"], index=["PJ", "Mob", "Boss"].index(entity.kind))
      level = st.number_input("Niveau", min_value=1, max_value=999, value=int(entity.level), step=1)

    with c2:
      hp_max = st.number_input("HP max", min_value=0.0, value=float(entity.hp_max), step=10.0)
      mp_max = st.number_input("MP max", min_value=0.0, value=float(entity.mp_max), step=5.0)
      hp = st.number_input("HP actuel", min_value=0.0, value=float(entity.hp), step=10.0)

    with c3:
      mp = st.number_input("MP actuel", min_value=0.0, value=float(entity.mp), step=5.0)
      STR = st.number_input("STR", min_value=0.0, value=float(entity.STR), step=1.0)
      VIT = st.number_input("VIT", min_value=0.0, value=float(entity.VIT), step=1.0)

    c4, c5, c6 = st.columns(3)
    with c4:
      AGI = st.number_input("AGI", min_value=0.0, value=float(entity.AGI), step=1.0)
    with c5:
      DEX = st.number_input("DEX", min_value=0.0, value=float(entity.DEX), step=1.0)
    with c6:
      INT = st.number_input("INT", min_value=0.0, value=float(entity.INT), step=1.0)

    submitted = st.form_submit_button("Enregistrer modifications")
    if submitted:
      # Mise à jour in-place
      entity.name = name
      entity.kind = kind
      entity.level = int(level)

      entity.hp_max = float(hp_max)
      entity.mp_max = float(mp_max)
      entity.hp = min(float(hp), float(entity.hp_max))
      entity.mp = min(float(mp), float(entity.mp_max))

      entity.STR = float(STR)
      entity.VIT = float(VIT)
      entity.AGI = float(AGI)
      entity.DEX = float(DEX)
      entity.INT = float(INT)

      on_save()
      st.success("Entité mise à jour.")
      st.rerun()
