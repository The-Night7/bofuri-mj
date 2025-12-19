import streamlit as st
from pathlib import Path

from src.storage import (
  load_settings,
  load_players, save_players,
  load_compendium, save_compendium,
  save_encounter, load_encounter_safe, list_encounters, new_encounter,
)
from src.md_parser import build_compendium_from_md

from src.ui import (
  render_compendium_summary,
  render_bestiaire_by_palier,
  render_player_editor,
  render_encounter_builder,
  render_turn_panel,
  render_action_panel,
  render_log_panel,
)
from src.rules import resolve_action


def _build_from_docs(docs_dir: Path):
  docs_dir = Path(docs_dir)
  bestiaire = docs_dir / "Bestiaire.md"
  skills = [docs_dir / f"palier{i}.md" for i in range(1, 7)]
  return build_compendium_from_md(bestiaire_path=bestiaire, skill_paths=skills)


def main() -> None:
  st.set_page_config(page_title="Bofuri RP — Encounter", layout="wide")

  settings = load_settings()
  docs_dir = Path(settings.get("docs_dir", "docs"))
  comp_path = settings.get("compendium_path", "data/compendium.json")

  st.sidebar.title("Bofuri RP")
  st.sidebar.caption(f"docs_dir: {docs_dir} | compendium: {comp_path}")

  # 1) Load compendium JSON (peut être vide)
  comp = load_compendium(comp_path)

  # Si compendium vide => on essaie de le générer depuis docs/
  if (not comp.monsters) and (not comp.skills):
    try:
      comp = _build_from_docs(docs_dir)
      save_compendium(comp, comp_path)
      st.sidebar.success("Compendium généré depuis docs/ + sauvegardé.")
    except Exception as e:
      st.sidebar.error("Impossible de générer le compendium depuis docs/")
      st.exception(e)
      return

  if st.sidebar.button("♻️ Regénérer compendium depuis docs/"):
    try:
      comp = _build_from_docs(docs_dir)
      save_compendium(comp, comp_path)
      st.sidebar.success("Compendium regénéré + sauvegardé.")
      st.rerun()
    except Exception as e:
      st.sidebar.error("Échec régénération compendium")
      st.exception(e)

  # Players
  players = load_players()

  # Encounter selection
  enc_choices = ["(nouveau)"] + list_encounters()
  enc_pick = st.sidebar.selectbox("Encounter", enc_choices, index=0)

  if enc_pick == "(nouveau)":
    if st.sidebar.button("➕ Créer encounter"):
      enc = new_encounter()
      st.sidebar.success(f"Encounter créé: {enc.encounter_id}")
      st.rerun()
    # placeholder non persistant tant qu'on ne crée pas
    enc = None
  else:
    enc = load_encounter_safe(enc_pick)

  def on_save_players() -> None:
    save_players(players)

  def on_save_encounter() -> None:
    if enc is None:
      return
    save_encounter(enc)

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
    if enc is None:
      st.info("Clique sur « Créer encounter » dans la sidebar pour démarrer.")
    else:
      render_encounter_builder(enc, players, comp, on_save_encounter)
      st.divider()
      render_log_panel(enc, on_save_encounter)

  with tab4:
    if enc is None:
      st.info("Aucun encounter chargé.")
    else:
      render_turn_panel(enc)
      st.divider()

      # Ton settings.json utilise vit_divisor_default
      vit_div = float(settings.get("vit_divisor_default", 100.0) or 100.0)

      render_action_panel(
        enc=enc,
        comp=comp,
        vit_div=vit_div,
        resolve_fn=resolve_action,
        on_save=on_save_encounter,
      )


if __name__ == "__main__":
  main()