import streamlit as st
from pathlib import Path

from src.models import Compendium, EncounterState
from src.storage import (
    load_settings, save_settings, load_compendium, save_compendium,
    load_players, save_players, load_encounter_safe, save_encounter,
    list_encounters, new_encounter
)
from src.ui import (
    render_compendium_summary, render_bestiaire_by_palier, render_player_editor,
    render_encounter_builder, render_turn_panel, render_action_panel, render_log_panel
)
from src.rules import resolve_attack
from src.md_parser import build_compendium_from_docs


def resolve_action(attacker, defender, roll_a, roll_b, perce_armure=False, vit_scale_div=100.0):
    return resolve_attack(
        attacker=attacker,
        defender=defender,
        roll_a=roll_a,
        roll_b=roll_b,
        attack_type="phys",  # TODO: supporter d'autres types
        perce_armure=perce_armure,
        vit_scale_div=vit_scale_div,
    )


def main():
    st.set_page_config(
        page_title="Système de combat",
        page_icon="🎲",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Système de combat")

    # Settings
    settings = load_settings()
    docs_dir = settings.get("docs_dir", "docs")
    compendium_path = settings.get("compendium_path", "data/compendium.json")

    # Sidebar
    st.sidebar.header("Configuration")

    # Compendium
    st.sidebar.subheader("Compendium")
    comp_source = st.sidebar.radio(
        "Source du compendium",
        ["Fichier JSON", "Dossier Markdown"],
        index=0
    )

    if comp_source == "Fichier JSON":
        comp = load_compendium(compendium_path)
        if st.sidebar.button("Recharger compendium JSON"):
            try:
                comp = load_compendium(compendium_path)
                st.sidebar.success("Compendium rechargé.")
            except Exception as e:
                st.sidebar.error("Échec chargement compendium")
                st.exception(e)
    else:
        # Chargement depuis Markdown
        try:
            comp = build_compendium_from_docs(docs_dir)
            if st.sidebar.button("Régénérer depuis Markdown"):
                try:
                    comp = build_compendium_from_docs(docs_dir)
                    save_compendium(comp, compendium_path)
                    st.sidebar.success("Compendium régénéré et sauvegardé.")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error("Échec régénération compendium")
                    st.exception(e)
        except Exception as e:
            st.sidebar.error("Échec chargement compendium depuis Markdown")
            st.exception(e)
            comp = Compendium(monsters={}, skills={})

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