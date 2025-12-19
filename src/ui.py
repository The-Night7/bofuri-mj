import streamlit as st
from typing import List, Callable, Optional

from .models import Player, Compendium, CombatantRef, RuntimeEntity


def render_log_panel() -> None:
  st.subheader("Log de combat")
  log = st.session_state.get("combat_log", [])
  if not log:
    st.caption("Le log apparaîtra ici.")
    return
  st.text("\n".join(log[-80:]))
  c1, c2 = st.columns([1, 1])
  if c1.button("Vider le log"):
    st.session_state.combat_log = []
    st.rerun()
  if c2.button("Afficher tout"):
    st.text("\n".join(log))


def render_compendium_summary(comp: Compendium) -> None:
  st.write({
    "Monstres": len(comp.monsters),
    "Skills": len(comp.skills),
  })
  if comp.monsters:
    # stats rapides
    lvls = []
    for m in comp.monsters.values():
      if m.variants:
        lvls.extend(list(m.variants.keys()))
    if lvls:
      st.caption(f"Niveaux variants min/max: {min(lvls)} → {max(lvls)}")


def render_monsters_browser(comp: Compendium) -> None:
  names = sorted(comp.monsters.keys())
  selected = st.selectbox("Monstre", names)
  m = comp.monsters[selected]

  st.markdown(f"### **{m.name}**")
  meta = {
    "Rareté": m.rarity or "—",
    "Niveaux": m.level_range or "—",
    "Zone": m.zone or "—",
    "Drops": ", ".join(m.drops or []) or "—",
  }
  st.write(meta)

  if m.abilities:
    st.markdown("#### Compétences")
    for a in m.abilities:
      st.write(f"- {a}")

  if not m.variants:
    st.warning("Aucune variante de niveau trouvée.")
    return

  lvls = sorted(m.variants.keys())
  lvl = st.selectbox("Variante de niveau", lvls, index=0, key=f"monster_lvl_{m.name}")
  v = m.variants[lvl]

  st.markdown("#### Stats (variante)")
  st.write({
    "HP max": v.hp_max,
    "MP max": v.mp_max,
    "STR": v.STR,
    "AGI": v.AGI,
    "INT": v.INT,
    "DEX": v.DEX,
    "VIT": v.VIT,
    "Attaque de base": v.base_attack if v.base_attack is not None else "—"
  })
  if v.extra:
    st.markdown("#### Extras (parsing brut)")
    st.write(v.extra)


def render_skills_browser(comp: Compendium) -> None:
  names = sorted(comp.skills.keys())
  selected = st.selectbox("Skill", names)
  s = comp.skills[selected]
  st.markdown(f"### **{s.name}**")
  st.write({
    "Palier": s.palier or "—",
    "Catégorie": s.category or "—",
    "Coût MP": s.cost_mp or "—",
    "Condition": s.condition or "—",
  })
  if s.description:
    st.markdown("#### Description")
    st.write(s.description)


def render_player_editor(players: List[Player], on_save: Callable[[], None]) -> None:
  if not players:
    st.info("Aucun PJ. Ajoute-en un ci-dessous.")

  # Liste + édition
  if players:
    names = [p.name for p in players]
    selected = st.selectbox("Choisir un PJ", names, index=0)
    p = next(x for x in players if x.name == selected)
    p.ensure_current()

    with st.form("edit_player"):
      c1, c2, c3 = st.columns(3)
      with c1:
        name = st.text_input("Nom", value=p.name)
        level = st.number_input("Niveau", min_value=1, max_value=999, value=int(p.level), step=1)
      with c2:
        hp_max = st.number_input("HP max", min_value=0.0, value=float(p.hp_max), step=10.0)
        mp_max = st.number_input("MP max", min_value=0.0, value=float(p.mp_max), step=5.0)
        hp = st.number_input("HP actuel", min_value=0.0, value=float(p.hp), step=10.0)
      with c3:
        mp = st.number_input("MP actuel", min_value=0.0, value=float(p.mp), step=5.0)
        STR = st.number_input("STR", min_value=0.0, value=float(p.STR), step=1.0)
        VIT = st.number_input("VIT", min_value=0.0, value=float(p.VIT), step=1.0)

      c4, c5, c6 = st.columns(3)
      with c4:
        AGI = st.number_input("AGI", min_value=0.0, value=float(p.AGI), step=1.0)
      with c5:
        DEX = st.number_input("DEX", min_value=0.0, value=float(p.DEX), step=1.0)
      with c6:
        INT = st.number_input("INT", min_value=0.0, value=float(p.INT), step=1.0)

      if st.form_submit_button("Enregistrer PJ"):
        p.name = name
        p.level = int(level)
        p.hp_max = float(hp_max)
        p.mp_max = float(mp_max)
        p.hp = min(float(hp), p.hp_max)
        p.mp = min(float(mp), p.mp_max)
        p.STR = float(STR); p.VIT = float(VIT)
        p.AGI = float(AGI); p.DEX = float(DEX); p.INT = float(INT)
        on_save()
        st.success("PJ sauvegardé.")
        st.rerun()

  st.divider()
  st.subheader("Ajouter un PJ")
  with st.form("add_player"):
    c1, c2 = st.columns(2)
    with c1:
      name = st.text_input("Nom (nouveau PJ)", value="Nouveau PJ")
      level = st.number_input("Niveau (nouveau PJ)", min_value=1, max_value=999, value=1, step=1)
      hp_max = st.number_input("HP max (nouveau PJ)", min_value=0.0, value=100.0, step=10.0)
      mp_max = st.number_input("MP max (nouveau PJ)", min_value=0.0, value=50.0, step=5.0)
    with c2:
      STR = st.number_input("STR (nouveau PJ)", min_value=0.0, value=10.0, step=1.0)
      VIT = st.number_input("VIT (nouveau PJ)", min_value=0.0, value=10.0, step=1.0)
      AGI = st.number_input("AGI (nouveau PJ)", min_value=0.0, value=10.0, step=1.0)
      DEX = st.number_input("DEX (nouveau PJ)", min_value=0.0, value=10.0, step=1.0)
      INT = st.number_input("INT (nouveau PJ)", min_value=0.0, value=10.0, step=1.0)

    if st.form_submit_button("Ajouter"):
      players.append(Player(
        name=name, level=int(level),
        hp_max=float(hp_max), mp_max=float(mp_max),
        STR=float(STR), VIT=float(VIT), AGI=float(AGI), DEX=float(DEX), INT=float(INT),
        hp=float(hp_max), mp=float(mp_max)
      ))
      on_save()
      st.success("PJ ajouté.")
      st.rerun()


def render_combatant_picker(label: str, players: List[Player], comp: Compendium, key_prefix: str) -> Optional[CombatantRef]:
  sources = ["PJ", "Monstre"]
  src = st.selectbox(f"{label} — Source", sources, key=f"{key_prefix}_src")

  if src == "PJ":
    if not players:
      st.warning("Aucun PJ disponible.")
      return None
    names = [p.name for p in players]
    name = st.selectbox(f"{label} — PJ", names, key=f"{key_prefix}_pj")
    return CombatantRef(ref_type="player", ref_name=name)

  # Monstre
  if not comp.monsters:
    st.warning("Compendium vide (pas de bestiaire importé).")
    return None

  mname = st.selectbox(f"{label} — Monstre", sorted(comp.monsters.keys()), key=f"{key_prefix}_mob")
  m = comp.monsters[mname]
  if not m.variants:
    st.warning("Ce monstre n'a pas de variantes de niveau.")
    return None

  lvls = sorted(m.variants.keys())
  lvl = st.selectbox(f"{label} — Niveau", lvls, key=f"{key_prefix}_mob_lvl")
  return CombatantRef(ref_type="monster", ref_name=mname, variant_level=int(lvl))


def render_combatant_panel(ref: Optional[CombatantRef], players: List[Player], comp: Compendium) -> None:
  if ref is None:
    st.caption("Aucun.")
    return

  rt = ref.to_runtime(players, comp)
  st.write({
    "Nom": rt.name,
    "Type": rt.kind,
    "Niveau": rt.level,
    "HP": f"{rt.hp:.2f}/{rt.hp_max:.2f}",
    "MP": f"{rt.mp:.2f}/{rt.mp_max:.2f}",
    "STR": rt.STR, "VIT": rt.VIT, "AGI": rt.AGI, "DEX": rt.DEX, "INT": rt.INT,
    "Attaque de base": rt.base_attack if rt.base_attack is not None else "—",
    "Zone": rt.zone or "—",
    "Drops": ", ".join(rt.drops or []) or "—",
  })
  if rt.abilities:
    st.markdown("**Compétences**")
    for a in rt.abilities:
      st.write(f"- {a}")
