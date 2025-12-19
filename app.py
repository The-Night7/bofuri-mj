import streamlit as st
from pathlib import Path

from src.storage import (
  load_settings,
  load_players, save_players,
  load_compendium, save_compendium,
  save_encounter, load_encounter, list_encounters,
)

# IMPORTANT: ton app importait build_compendium_from_docs -> on le garde
from src.md_parser import build_compendium_from_docs

from src.ui import (
  render_compendium_summary,
  render_bestiaire_by_palier,
  render_player_editor,
  render_encounter_builder,
  render_turn_panel,
  render_action_panel,
  render_log_panel,
)

from src.rules import resolve_attack as resolve_action


DOCS_DIR = Path("docs")


def main() -> None:
  st.set_page_config(page_title="Bofuri RP — Encounter", layout="wide")

  settings = load_settings()

  # ------- Sidebar
  st.sidebar.title("Bofuri RP")
  st.sidebar.caption("Compendium = Bestiaire.md + palier1..6.md")

  # (1) Load persisted JSON compendium if exists, else build from docs
  comp = load_compendium()
  if comp is None:
    try:
      comp = build_compendium_from_docs(DOCS_DIR)
      save_compendium(comp)
      st.sidebar.success("Compendium généré depuis docs/ puis sauvegardé.")
    except Exception as e:
      st.sidebar.error("Impossible de générer le compendium depuis docs/.")
      st.exception(e)
      return

  # (2) Button to force rebuild
  if st.sidebar.button("♻️ Regénérer compendium depuis docs/"):
    try:
      comp = build_compendium_from_docs(DOCS_DIR)
      save_compendium(comp)
      st.sidebar.success("Compendium regénéré + sauvegardé.")
      st.rerun()
    except Exception as e:
      st.sidebar.error("Echec regeneration compendium.")
      st.exception(e)

  # Players
  players = load_players()

  # Encounter
  enc_id = st.sidebar.selectbox("Encounter", ["(nouveau)"] + list_encounters())
  if enc_id == "(nouveau)":
    enc = load_encounter(None)  # ton storage peut ignorer / créer
  else:
    enc = load_encounter(enc_id)

  # Save hooks
  def on_save_players() -> None:
    save_players(players)

  def on_save_encounter() -> None:
    save_encounter(enc)

  # ------- Main UI
  tab1, tab2, tab3, tab4 = st.tabs(["Compendium", "PJ", "Encounter", "Combat"])

  with tab1:
    st.subheader("Compendium")
    render_compendium_summary(comp)
    st.divider()
    render_bestiaire_by_palier(comp)

  with tab2:
    st.subheader("Éditeur PJ")
    render_player_editor(players, on_save_players)

  with tab3:
    render_encounter_builder(enc, players, comp, on_save_encounter)
    st.divider()
    render_log_panel(enc, on_save_encounter)

  with tab4:
    render_turn_panel(enc)
    st.divider()

    vit_div = float(settings.get("vit_div", 1.0) or 1.0)

    render_action_panel(
      enc=enc,
      comp=comp,
      vit_div=vit_div,
      resolve_fn=resolve_action,
      on_save=on_save_encounter,
    )


if __name__ == "__main__":
  main()