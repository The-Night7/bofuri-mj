import time
import uuid
import random
import streamlit as st
from typing import List, Callable, Optional, Dict

from .models import (
    Player, Compendium, Monster,
    EncounterState, Participant, RuntimeEntity, ActionLogEntry
)
from .variant_interp import interpolated_variant


# ----------------------------
# Helpers / Panels
# ----------------------------

def render_log_panel(enc: EncounterState, on_save: Callable[[], None]) -> None:
    st.subheader("Journal du combat (persistant)")
    st.caption("Chaque action (attaque/skill) est enregistrée avec round, tour, rolls et résultat.")

    if not enc.log:
        st.caption("Aucune action enregistrée.")
        return

    last = enc.log[-80:]
    st.text("\n".join([
        f"[R{e.round} T{e.turn_index}] {e.actor_name} -> {e.target_name or '—'} | "
        f"{e.action_type}{' (' + e.skill_name + ')' if e.skill_name else ''} | "
        f"x={e.roll_a} y={e.roll_b} | hit={e.result.get('hit')}"
        for e in last
    ]))

    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("Sauvegarder encounter maintenant"):
        on_save()
        st.success("Encounter sauvegardé.")
    if c2.button("Tout afficher (brut JSON)"):
        st.json(enc.to_dict())
    if c3.button("Vider log (attention)"):
        enc.log = []
        on_save()
        st.rerun()


def render_compendium_summary(comp: Compendium) -> None:
    st.write({"Monstres": len(comp.monsters), "Skills": len(comp.skills)})


def _sorted_paliers(monsters: Dict[str, Monster]) -> List[str]:
    by_palier: Dict[str, List[Monster]] = {}
    for m in monsters.values():
        by_palier.setdefault(m.palier or "Palier ?", []).append(m)
    return sorted(by_palier.keys(), key=lambda x: (999 if "?" in x else int(x.split()[-1])))


def render_bestiaire_by_palier(comp: Compendium) -> None:
    """
    Affiche le bestiaire organisé par palier
    """
    # Regrouper les monstres par palier
    paliers = {}
    for monster_key, monster in comp.monsters.items():
        palier = monster.palier or "Inconnu"
        if palier not in paliers:
            paliers[palier] = []
        paliers[palier].append((monster_key, monster))

    # Trier les paliers
    sorted_paliers = sorted(paliers.keys())

    # Créer un accordéon pour chaque palier
    for palier in sorted_paliers:
        with st.expander(f"{palier} ({len(paliers[palier])} monstres)"):
            # Afficher les monstres de ce palier
            for monster_key, monster in paliers[palier]:
                col1, col2 = st.columns([1, 3])

                with col1:
                    st.markdown(f"### {monster.name}")
                    if monster.level_range:
                        st.write(f"Niveau: {monster.level_range}")
                    if monster.rarity:
                        st.write(f"Rareté: {monster.rarity}")
                    if monster.zone:
                        st.write(f"Zone: {monster.zone}")

                with col2:
                    # Afficher les variantes si disponibles
                    if monster.variants and len(monster.variants) > 0:
                        # Créer des onglets pour chaque variante
                        variant_levels = sorted(monster.variants.keys())
                        tabs = st.tabs([f"Niveau {lvl}" for lvl in variant_levels])

                        for i, lvl in enumerate(variant_levels):
                            variant = monster.variants[lvl]
                            with tabs[i]:
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.write(f"**HP**: {variant.hp_max}")
                                    st.write(f"**MP**: {variant.mp_max}")
                                    st.write(f"**Base Attack**: {variant.base_attack}")
                                with col_b:
                                    st.write(f"**STR**: {variant.STR}")
                                    st.write(f"**AGI**: {variant.AGI}")
                                    st.write(f"**INT**: {variant.INT}")
                                    st.write(f"**DEX**: {variant.DEX}")
                                    st.write(f"**VIT**: {variant.VIT}")
                    else:
                        # Si pas de variantes, afficher les stats depuis les abilities
                        if monster.abilities:
                            # Extraire les stats des abilities
                            from src.variant_interp import _extract_stats_from_abilities, _extract_level_from_range

                            stats = _extract_stats_from_abilities(monster.abilities)
                            monster_level = _extract_level_from_range(monster.level_range)

                            st.write(f"**Niveau estimé**: {monster_level}")

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.write(f"**HP**: {stats['hp_max']}")
                                st.write(f"**MP**: {stats['mp_max']}")
                                if stats['base_attack'] > 0:
                                    st.write(f"**Base Attack**: {stats['base_attack']}")
                            with col_b:
                                st.write(f"**STR**: {stats['STR']}")
                                st.write(f"**AGI**: {stats['AGI']}")
                                st.write(f"**INT**: {stats['INT']}")
                                st.write(f"**DEX**: {stats['DEX']}")
                                st.write(f"**VIT**: {stats['VIT']}")

                    # Afficher les drops et capacités
                    if monster.drops:
                        st.write("**Drops:**")
                        for drop in monster.drops:
                            st.write(f"- {drop}")

                    if monster.abilities:
                        st.write("**Capacités:**")
                        for ability in monster.abilities:
                            st.write(f"- {ability}")

                st.divider()


def render_player_editor(players: List[Player], on_save: Callable[[], None]) -> None:
    if not players:
        st.info("Aucun PJ.")

    if players:
        names = [p.name for p in players]
        selected = st.selectbox("Choisir un PJ", names, index=0, key="pj_pick")
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

            submitted = st.form_submit_button("Enregistrer PJ")
            if submitted:
                p.name = name
                p.level = int(level)
                p.hp_max = float(hp_max)
                p.mp_max = float(mp_max)
                p.hp = min(float(hp), p.hp_max)
                p.mp = min(float(mp), p.mp_max)
                p.STR = float(STR)
                p.VIT = float(VIT)
                p.AGI = float(AGI)
                p.DEX = float(DEX)
                p.INT = float(INT)

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
                hp=float(hp_max), mp=float(mp_max),
            ))
            on_save()
            st.success("PJ ajouté.")
            st.rerun()


# ----------------------------
# Encounter UI
# ----------------------------

def _player_to_runtime(p: Player) -> RuntimeEntity:
    p.ensure_current()
    return RuntimeEntity(
        name=p.name, kind="PJ", level=p.level,
        hp_max=p.hp_max, mp_max=p.mp_max,
        STR=p.STR, AGI=p.AGI, INT=p.INT, DEX=p.DEX, VIT=p.VIT,
        hp=float(p.hp), mp=float(p.mp),
    )


def _monster_to_runtime(m: Monster, lvl: int) -> RuntimeEntity:
    v = interpolated_variant(m, int(lvl))
    if v is None:
        # Fallback minimal (évite crash UI)
        return RuntimeEntity(
            name=f"{m.name} (Lvl {lvl})",
            kind="Mob",
            level=int(lvl),
            hp_max=0.0,
            mp_max=0.0,
            STR=0.0,
            AGI=0.0,
            INT=0.0,
            DEX=0.0,
            VIT=0.0,
            hp=0.0,
            mp=0.0,
        )

    return RuntimeEntity(
        name=f"{m.name} (Lvl {lvl})",
        kind="Boss" if (m.rarity and "boss" in (m.rarity or "").lower()) else "Mob",
        level=int(lvl),
        hp_max=float(v["hp_max"]),
        mp_max=float(v["mp_max"]),
        STR=float(v["STR"]),
        AGI=float(v["AGI"]),
        INT=float(v["INT"]),
        DEX=float(v["DEX"]),
        VIT=float(v["VIT"]),
        hp=float(v["hp_max"]),
        mp=float(v["mp_max"]),
        base_attack=v.get("base_attack"),
        zone=m.zone,
        drops=m.drops,
        abilities=m.abilities,
        extra=v.get("extra") or {},
    )


def _monster_to_runtime_manual(
        m: Monster,
        lvl: int,
        stats: Dict[str, float],
        base_attack: Optional[float],
) -> RuntimeEntity:
    return RuntimeEntity(
        name=f"{m.name} (Lvl {lvl})",
        kind="Boss" if (m.rarity and "boss" in (m.rarity or "").lower()) else "Mob",
        level=int(lvl),
        hp_max=float(stats["hp_max"]),
        mp_max=float(stats["mp_max"]),
        STR=float(stats["STR"]),
        AGI=float(stats["AGI"]),
        INT=float(stats["INT"]),
        DEX=float(stats["DEX"]),
        VIT=float(stats["VIT"]),
        hp=float(stats["hp_max"]),
        mp=float(stats["mp_max"]),
        base_attack=base_attack,
        zone=m.zone,
        drops=m.drops,
        abilities=m.abilities,
        extra={},
    )


def render_encounter_builder(enc: EncounterState, players: List[Player], comp: Compendium, on_save) -> None:
    """
    Interface pour construire un encounter
    """
    st.subheader("Builder")

    # Afficher les participants actuels
    if enc.participants:
        st.write("### Participants")
        cols = st.columns(4)
        for i, p in enumerate(enc.participants):
            with cols[i % 4]:
                st.write(f"**{p.runtime.name}** ({p.side})")
                st.write(f"Lvl {p.runtime.level} - {p.runtime.kind}")
                st.write(f"HP: {p.runtime.hp}/{p.runtime.hp_max}")
                st.write(f"MP: {p.runtime.mp}/{p.runtime.mp_max}")
                if st.button("❌", key=f"remove_{p.id}"):
                    enc.participants = [x for x in enc.participants if x.id != p.id]
                    on_save()
                    st.rerun()

    # Ajouter un joueur
    st.write("### Ajouter un joueur")
    if not players:
        st.warning("Aucun joueur défini. Créez-en dans l'onglet PJ.")
    else:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            player_idx = st.selectbox("Joueur", range(len(players)), format_func=lambda i: players[i].name)
        with col2:
            reset_hp = st.checkbox("Reset HP/MP", value=True)
        with col3:
            if st.button("➕ Ajouter PJ"):
                player = players[player_idx]

                # Créer une RuntimeEntity à partir du Player
                runtime = RuntimeEntity(
                    name=player.name,
                    kind="PJ",
                    level=player.level,
                    hp_max=player.hp_max,
                    mp_max=player.mp_max,
                    STR=player.STR,
                    AGI=player.AGI,
                    INT=player.INT,
                    DEX=player.DEX,
                    VIT=player.VIT,
                    hp=player.hp_max if reset_hp else (player.hp or player.hp_max),
                    mp=player.mp_max if reset_hp else (player.mp or player.mp_max)
                )

                # Ajouter le participant
                enc.participants.append(
                    Participant(
                        id=str(uuid.uuid4()),
                        side="player",
                        runtime=runtime
                    )
                )
                on_save()
                st.rerun()

    # Ajouter un monstre
    st.write("### Ajouter un monstre")
    if not comp.monsters:
        st.warning("Aucun monstre dans le compendium.")
    else:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        # Liste des monstres
        monster_names = [m.name for m in comp.monsters.values()]
        monster_keys = list(comp.monsters.keys())

        with col1:
            monster_idx = st.selectbox("Monstre", range(len(monster_names)), format_func=lambda i: monster_names[i])

        monster_key = monster_keys[monster_idx]
        monster = comp.monsters[monster_key]

        # Déterminer les niveaux disponibles
        if monster.variants and len(monster.variants) > 0:
            available_levels = sorted(monster.variants.keys())
            default_level = available_levels[0]
        else:
            # Si pas de variantes, utiliser le niveau estimé à partir du level_range
            from src.variant_interp import _extract_level_from_range
            default_level = _extract_level_from_range(monster.level_range)
            available_levels = [default_level]

        with col2:
            # Niveau du monstre
            level = st.number_input("Niveau", min_value=1, value=default_level, step=1)

        with col3:
            # Type de monstre (normal, élite, boss)
            kind = st.selectbox("Type", ["Mob", "Elite", "Boss"])

        with col4:
            if st.button("➕ Ajouter monstre"):
                # Obtenir les stats du monstre pour ce niveau
                from src.variant_interp import interpolated_variant

                variant_data = interpolated_variant(monster, level)

                if variant_data:
                    # Créer une RuntimeEntity à partir des données de la variante
                    runtime = RuntimeEntity(
                        name=monster.name,
                        kind=kind,
                        level=variant_data["level"],
                        hp_max=variant_data["hp_max"],
                        mp_max=variant_data["mp_max"],
                        STR=variant_data["STR"],
                        AGI=variant_data["AGI"],
                        INT=variant_data["INT"],
                        DEX=variant_data["DEX"],
                        VIT=variant_data["VIT"],
                        hp=variant_data["hp_max"],
                        mp=variant_data["mp_max"],
                        base_attack=variant_data.get("base_attack"),
                        zone=monster.zone,
                        drops=monster.drops,
                        abilities=monster.abilities,
                        extra=variant_data.get("extra")
                    )

                    # Ajouter le participant
                    enc.participants.append(
                        Participant(
                            id=str(uuid.uuid4()),
                            side="mob",
                            runtime=runtime
                        )
                    )
                    on_save()
                    st.rerun()
                else:
                    st.error(f"Impossible de créer une variante pour {monster.name} niveau {level}")


def render_turn_panel(enc: EncounterState) -> None:
    enc.recompute_round()
    actor = enc.current_actor()
    st.markdown("### Tour actuel")
    if actor is None:
        st.info("Personne ne peut jouer (encounter vide ou tous morts).")
        return

    st.write({
        "Round": enc.round,
        "Turn index (action)": enc.turn_index,
        "Acteur": actor.runtime.name,
        "Camp": actor.side,
        "HP": f"{actor.runtime.hp:.1f}/{actor.runtime.hp_max:.1f}",
        "MP": f"{actor.runtime.mp:.1f}/{actor.runtime.mp_max:.1f}",
    })


def render_action_panel(enc: EncounterState, comp: Compendium, vit_div: float, resolve_fn, on_save) -> None:
    """
    Panneau d'action pour le combat
    """
    st.subheader("Action")

    actor = enc.current_actor()
    if not actor:
        st.warning("Aucun participant actif.")
        return

    # Liste des participants vivants qui ne sont pas l'acteur courant
    targets = [p for p in enc.alive_participants() if p.id != actor.id]
    if not targets:
        st.warning("Aucune cible disponible.")
        return

    # Affichage de l'acteur courant
    st.write(f"**Tour de {actor.runtime.name}** (niveau {actor.runtime.level})")

    # Sélection de la cible
    target_names = [p.runtime.name for p in targets]
    target_idx = st.selectbox("Cible", range(len(targets)), format_func=lambda i: target_names[i])
    target = targets[target_idx]

    # Type d'action
    action_type = st.radio(
        "Type d'action",
        ["Attaque de base", "Compétence"],
        horizontal=True
    )

    if action_type == "Attaque de base":
        # Sélection du type d'attaque
        attack_type = st.radio(
            "Type d'attaque",
            ["Physique (STR)", "Magique (INT)", "À distance (DEX)"],
            horizontal=True
        )

        # Conversion du type d'attaque pour le système de règles
        attack_type_map = {
            "Physique (STR)": "phys",
            "Magique (INT)": "magic",
            "À distance (DEX)": "ranged"
        }
        attack_type_value = attack_type_map[attack_type]

        # Affichage de la statistique utilisée pour l'attaque
        if attack_type == "Physique (STR)":
            st.info(f"Utilise STR: {actor.runtime.STR}")
        elif attack_type == "Magique (INT)":
            st.info(f"Utilise INT: {actor.runtime.INT}")
        elif attack_type == "À distance (DEX)":
            st.info(f"Utilise DEX: {actor.runtime.DEX}")

        # Option perce-armure
        perce_armure = st.checkbox("Perce-armure", value=False, help="Ignore partiellement la défense de la cible")

        # Jets de dés
        col1, col2 = st.columns(2)
        with col1:
            roll_a = st.number_input("Jet d'attaque", min_value=1.0, max_value=20.0, value=10.0, step=1.0)
        with col2:
            roll_b = st.number_input("Jet de défense", min_value=1.0, max_value=20.0, value=10.0, step=1.0)

        # Bouton d'action
        if st.button(f"⚔️ Attaquer {target.runtime.name}"):
            result = resolve_fn(
                attacker=actor.runtime,
                defender=target.runtime,
                roll_a=roll_a,
                roll_b=roll_b,
                attack_type=attack_type_value,
                perce_armure=perce_armure,
                vit_scale_div=vit_div
            )

            # Création d'une entrée de log
            log_entry = ActionLogEntry(
                ts=time.time(),
                round=enc.round,
                turn_index=enc.turn_index,
                actor_id=actor.id,
                actor_name=actor.runtime.name,
                target_id=target.id,
                target_name=target.runtime.name,
                action_type="basic_attack",
                skill_name=None,
                roll_a=roll_a,
                roll_b=roll_b,
                perce_armure=perce_armure,
                vit_div=vit_div,
                result=result
            )

            # Ajout au log et passage au tour suivant
            enc.log.append(log_entry)
            enc.next_turn()
            on_save()
            st.rerun()

    else:  # Compétence
        st.info("Système de compétences à implémenter")

        # Placeholder pour le système de compétences
        if st.button("Passer le tour"):
            enc.next_turn()
            on_save()
            st.rerun()

# End of file