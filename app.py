import streamlit as st

from src.storage import (
  load_settings, load_players, save_players,
  load_compendium, save_compendium,
  save_encounter, load_encounter, list_encounters
)
from src.md_parser import build_compendium_from_docs
from src.models import EncounterState
from src.rules import resolve_attack
from src.ui import (
  render_player_editor,
  render_compendium_summary,
  render_bestiaire_by_palier,
  render_encounter_builder,
  render_turn_panel,
  render_action_panel,
  render_log_panel,
)


def main():
  st.set_page_config(page_title="Bofuri RP — Assistant MJ (V3)", layout="wide")
  st.title("Assistant MJ — Bofuri RP (V3: Encounter multi-combat)")

  settings = load_settings()
  players = load_players()
  compendium = load_compendium(settings.get("compendium_path", "data/compendium.json"))

  # Encounter state in session
  if "encounter" not in st.session_state:
    st.session_state.encounter = EncounterState()

  enc: EncounterState = st.session_state.encounter

  def save_enc():
    save_encounter(enc)

  tabs = st.tabs(["⚔️ Encounter (Combat)", "🐾 Bestiaire", "🧰 Import & Admin", "👤 PJ"])

  # ---------------- Combat
  with tabs[0]:
    left, right = st.columns([1, 1])

    with left:
      st.subheader("Gestion Encounter")
      st.caption(f"Encounter ID: {enc.encounter_id}")

      render_encounter_builder(enc, players, compendium, on_save=save_enc)

      st.divider()
      st.subheader("Chargement / Sauvegardes")
      existing = list_encounters()
      c1, c2 = st.columns([1, 1])
      with c1:
        if st.button("Sauvegarder l'encounter maintenant"):
          save_enc()
          st.success("Sauvegardé.")
      with c2:
        if existing:
          chosen = st.selectbox("Charger un encounter", ["—"] + existing)
          if chosen != "—" and st.button("Charger"):
            st.session_state.encounter = load_encounter(chosen)
            st.rerun()
        else:
          st.caption("Aucun encounter sauvegardé.")

    with right:
      st.subheader("Tour / Actions")
      vit_div = st.number_input(
        "Diviseur VIT (VIT/?)",
        min_value=1.0, max_value=100000.0,
        value=float(settings.get("vit_divisor_default", 100.0)),
        step=1.0
      )

      render_turn_panel(enc)
      st.divider()
      render_action_panel(
        enc=enc,
        comp=compendium,
        vit_div=float(vit_div),
        resolve_fn=resolve_attack,
        on_save=save_enc
      )

      st.divider()
      render_log_panel(enc, on_save=save_enc)

      st.divider()
      st.subheader("Sync PV PJ")
      st.caption("Les PJ dans l'encounter ne modifient pas automatiquement players.json : clique ici pour appliquer les PV/PM actuels aux PJ persistants.")
      if st.button("Appliquer PV/PM encounter → players.json"):
        # match by name exact
        name_to_p = {p.name: p for p in players}
        for part in enc.participants:
          if part.side == "player" and part.runtime.name in name_to_p:
            p = name_to_p[part.runtime.name]
            p.hp = float(part.runtime.hp)
            p.mp = float(part.runtime.mp)
        save_players(players)
        st.success("players.json mis à jour.")

  # ---------------- Bestiaire
  with tabs[1]:
    st.subheader("Bestiaire (par Palier, niveaux progressifs)")
    if not compendium.monsters:
      st.info("Compendium vide. Va dans Import & Admin.")
    else:
      render_bestiaire_by_palier(compendium)

  # ---------------- Import
  with tabs[2]:
    st.subheader("Import docs/ → Compendium")
    st.write(f"Dossier docs: `{settings.get('docs_dir', 'docs')}/`")

    if st.button("Importer / Rebuild compendium.json", type="primary"):
      comp = build_compendium_from_docs(settings.get("docs_dir", "docs"))
      save_compendium(comp, settings.get("compendium_path", "data/compendium.json"))
      st.success("Compendium reconstruit.")
      st.rerun()

    st.divider()
    render_compendium_summary(compendium)

  # ---------------- PJ
  with tabs[3]:
    st.subheader("PJ (persistants)")
    render_player_editor(players, on_save=lambda: save_players(players))


if __name__ == "__main__":
  main()
