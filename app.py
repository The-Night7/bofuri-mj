import streamlit as st

from src.storage import (
  load_settings,
  load_players,
  save_players,
  load_compendium,
  save_compendium,
)
from src.md_parser import build_compendium_from_docs
from src.models import CombatantRef
from src.rules import resolve_attack
from src.ui import (
  render_player_editor,
  render_compendium_summary,
  render_skills_browser,
  render_monsters_browser,
  render_combatant_picker,
  render_combatant_panel,
  render_log_panel,
)


def main():
  st.set_page_config(page_title="Bofuri RP — Assistant MJ (V2)", layout="wide")
  st.title("Assistant MJ — Bofuri RP (V2)")

  settings = load_settings()
  players = load_players()
  compendium = load_compendium()

  if "combat_log" not in st.session_state:
    st.session_state.combat_log = []
  if "last_result" not in st.session_state:
    st.session_state.last_result = None

  tabs = st.tabs(["⚔️ Combat", "🐾 Bestiaire", "📚 Skills", "🧰 Import & Admin"])

  # -------------------- Combat
  with tabs[0]:
    left, right = st.columns([1, 1])

    with left:
      st.subheader("Sélection des combattants")
      a_ref = render_combatant_picker("A (Attaquant)", players, compendium, key_prefix="A")
      b_ref = render_combatant_picker("B (Défenseur)", players, compendium, key_prefix="B")

      st.divider()
      c1, c2 = st.columns(2)
      with c1:
        st.subheader("A — Détails")
        render_combatant_panel(a_ref, players, compendium)
      with c2:
        st.subheader("B — Détails")
        render_combatant_panel(b_ref, players, compendium)

    with right:
      st.subheader("Résolution (duel de rolls)")

      vit_div = st.number_input(
        "Diviseur VIT (VIT/?)",
        min_value=1.0,
        max_value=100000.0,
        value=float(settings.get("vit_divisor_default", 100.0)),
        step=1.0
      )
      perce_armure = st.checkbox("Skill: Perce-armure (ignore VIT B dans les dégâts)", value=False)

      c1, c2 = st.columns(2)
      with c1:
        roll_a = st.number_input("Roll A (x)", min_value=0.0, max_value=10000.0, value=10.0, step=1.0)
      with c2:
        roll_b = st.number_input("Roll B (y)", min_value=0.0, max_value=10000.0, value=10.0, step=1.0)

      # Boutons
      b1, b2, b3 = st.columns([1, 1, 1])
      do_resolve = b1.button("Résoudre l'attaque", type="primary")
      do_reset_players = b2.button("Reset PV/PM (PJ)")
      do_save_players = b3.button("Sauvegarder PJ")

      if do_reset_players:
        for p in players:
          p.reset()
        save_players(players)
        st.success("PV/PM PJ reset + sauvegardés.")
        st.rerun()

      if do_save_players:
        save_players(players)
        st.success("PJ sauvegardés.")

      if do_resolve:
        if a_ref is None or b_ref is None:
          st.error("Choisis A et B.")
        else:
          # Récupère des 'snapshots' combat (les monstres ne sont pas persistés en PV/PM)
          a = a_ref.to_runtime(players, compendium)
          b = b_ref.to_runtime(players, compendium)

          result = resolve_attack(
            attacker=a,
            defender=b,
            roll_a=roll_a,
            roll_b=roll_b,
            perce_armure=perce_armure,
            vit_scale_div=vit_div
          )

          st.session_state.last_result = result
          st.session_state.combat_log.extend(result["effects"])

          # Si A ou B est un PJ : on applique les PV au PJ (persistant)
          a_ref.apply_runtime_back(a, players)
          b_ref.apply_runtime_back(b, players)

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

      st.divider()
      render_log_panel()

  # -------------------- Bestiaire
  with tabs[1]:
    st.subheader("Bestiaire (compendium)")
    if not compendium.monsters:
      st.info("Compendium vide. Va dans l’onglet Import & Admin puis clique 'Importer docs/'.")
    else:
      render_monsters_browser(compendium)

  # -------------------- Skills
  with tabs[2]:
    st.subheader("Skills (compendium)")
    if not compendium.skills:
      st.info("Aucun skill chargé. Va dans l’onglet Import & Admin puis clique 'Importer docs/'.")
    else:
      render_skills_browser(compendium)

  # -------------------- Import & Admin
  with tabs[3]:
    st.subheader("Import depuis docs/")
    st.write(f"📁 Dossier docs: `{settings.get('docs_dir', 'docs')}/`")

    c1, c2 = st.columns([1, 1])
    with c1:
      if st.button("Importer docs/ → Générer compendium.json", type="primary"):
        comp = build_compendium_from_docs(settings.get("docs_dir", "docs"))
        save_compendium(comp, settings.get("compendium_path", "data/compendium.json"))
        st.success("Compendium généré et sauvegardé.")
        st.rerun()

    with c2:
      if st.button("Charger compendium.json existant"):
        st.rerun()

    st.divider()
    st.subheader("Résumé")
    render_compendium_summary(compendium)

    st.divider()
    st.subheader("Éditeur PJ (persistant)")
    render_player_editor(players, on_save=lambda: save_players(players))


if __name__ == "__main__":
  main()
