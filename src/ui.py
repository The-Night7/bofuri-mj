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
  if not comp.monsters:
    st.info("Compendium vide.")
    return

  # group by palier
  by_palier: Dict[str, List[Monster]] = {}
  for m in comp.monsters.values():
    p = m.palier or "Palier ?"
    by_palier.setdefault(p, []).append(m)

  paliers_sorted = sorted(by_palier.keys(), key=lambda x: (999 if "?" in x else int(x.split()[-1])))
  palier = st.selectbox("Palier", paliers_sorted, key="best_palier")

  mobs = sorted(by_palier[palier], key=lambda mm: mm.name.lower())
  name = st.selectbox("Monstre", [mm.name for mm in mobs], key="best_monster")
  m = comp.monsters[name]

  st.markdown(f"### **{m.name}**")
  st.write({
    "Palier": m.palier or "—",
    "Niveaux": m.level_range or "—",
    "Rareté": m.rarity or "—",
    "Zone": m.zone or "—",
    "Drops": ", ".join(m.drops or []) or "—",
  })

  if m.abilities:
    st.markdown("#### Compétences (bestiaire)")
    for a in m.abilities:
      st.write(f"- {a}")

  if not m.variants:
    st.warning("Pas de variantes de niveau détectées pour ce monstre.")
    return

  lvls = sorted(int(k) for k in m.variants.keys())
  if len(lvls) >= 2:
    lvl = st.slider(
      "Niveau (progressif)",
      min_value=int(lvls[0]),
      max_value=int(lvls[-1]),
      value=int(lvls[0]),
      key="best_lvl_slider",
    )
  else:
    # Streamlit interdit slider min==max
    only = int(lvls[0])
    st.caption("Monstre avec une seule variante de niveau.")
    lvl = st.number_input(
      "Niveau",
      min_value=only,
      max_value=only,
      value=only,
      step=1,
      disabled=True,
      key="best_lvl_single",
    )

  v = interpolated_variant(m, int(lvl))
  if v is None:
    st.warning("Aucun variant disponible")
    return

  st.markdown("#### Stats")
  st.write({
    "HP max": v["hp_max"],
    "MP max": v["mp_max"],
    "STR": v["STR"],
    "AGI": v["AGI"],
    "INT": v["INT"],
    "DEX": v["DEX"],
    "VIT": v["VIT"],
    "Attaque de base": (v.get("base_attack") if v.get("base_attack") is not None else "—"),
    "Extra": v.get("extra") or {},
  })


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


def render_encounter_builder(
  enc: EncounterState,
  players: List[Player],
  comp: Compendium,
  on_save: Callable[[], None],
) -> None:
  st.subheader("Préparer l'encounter (multi-PJ / multi-mobs)")

  c1, c2 = st.columns(2)
  with c1:
    st.markdown("### Ajouter un PJ")
    if not players:
      st.warning("Aucun PJ dans players.json")
    else:
      pname = st.selectbox("PJ", [p.name for p in players], key="enc_add_pj")
      if st.button("Ajouter PJ à l'encounter", key="btn_add_pj"):
        p = next(x for x in players if x.name == pname)
        rt = _player_to_runtime(p)
        enc.participants.append(Participant(id=str(uuid.uuid4()), side="player", runtime=rt))
        enc.recompute_round()
        on_save()
        st.rerun()

  with c2:
    st.markdown("### Ajouter un mob")
    if not comp.monsters:
      st.warning("Compendium vide.")
    else:
      by_palier: Dict[str, List[Monster]] = {}
      for m in comp.monsters.values():
        by_palier.setdefault(m.palier or "Palier ?", []).append(m)

      paliers = sorted(by_palier.keys(), key=lambda x: (999 if "?" in x else int(x.split()[-1])))
      pal = st.selectbox("Palier", paliers, key="enc_add_mob_palier")
      mname = st.selectbox("Monstre", sorted([mm.name for mm in by_palier[pal]]), key="enc_add_mob_name")
      m = comp.monsters[mname]

      # CAS 1 — variantes présentes
      if m.variants:
        lvls = sorted(int(k) for k in m.variants.keys())
        if len(lvls) >= 2:
          lvl = st.slider(
            "Niveau",
            min_value=int(lvls[0]),
            max_value=int(lvls[-1]),
            value=int(lvls[0]),
            key="enc_add_mob_lvl",
          )
        else:
          only = int(lvls[0])
          st.caption("Monstre avec une seule variante de niveau.")
          lvl = st.number_input(
            "Niveau",
            min_value=only,
            max_value=only,
            value=only,
            step=1,
            disabled=True,
            key="enc_add_mob_lvl_single",
          )

        if st.button("Ajouter Mob à l'encounter", key="btn_add_mob"):
          rt = _monster_to_runtime(m, int(lvl))
          enc.participants.append(Participant(id=str(uuid.uuid4()), side="mob", runtime=rt))
          enc.recompute_round()
          on_save()
          st.rerun()

      # CAS 2 — pas de variantes => fallback manuel (au cas où)
      else:
        st.warning("Ce monstre n'a pas de variantes. Ajout possible via saisie manuelle des stats.")
        lvl = st.number_input(
          "Niveau (manuel)",
          min_value=1,
          max_value=999,
          value=1,
          step=1,
          key="enc_add_mob_lvl_manual",
        )

        cA, cB, cC = st.columns(3)
        with cA:
          hp_max = st.number_input("HP max", min_value=0.0, value=50.0, step=10.0, key="enc_mob_hp")
          mp_max = st.number_input("MP max", min_value=0.0, value=10.0, step=5.0, key="enc_mob_mp")
          base_attack = st.number_input("Attaque de base (optionnel)", min_value=0.0, value=0.0, step=1.0, key="enc_mob_ba")
        with cB:
          STR = st.number_input("STR", min_value=0.0, value=5.0, step=1.0, key="enc_mob_str")
          VIT = st.number_input("VIT", min_value=0.0, value=5.0, step=1.0, key="enc_mob_vit")
        with cC:
          AGI = st.number_input("AGI", min_value=0.0, value=5.0, step=1.0, key="enc_mob_agi")
          DEX = st.number_input("DEX", min_value=0.0, value=5.0, step=1.0, key="enc_mob_dex")
          INT = st.number_input("INT", min_value=0.0, value=5.0, step=1.0, key="enc_mob_int")

        if st.button("Ajouter Mob (manuel) à l'encounter", key="btn_add_mob_manual"):
          stats = {"hp_max": hp_max, "mp_max": mp_max, "STR": STR, "AGI": AGI, "INT": INT, "DEX": DEX, "VIT": VIT}
          rt = _monster_to_runtime_manual(
            m=m,
            lvl=int(lvl),
            stats=stats,
            base_attack=(float(base_attack) if float(base_attack) > 0 else None),
          )
          enc.participants.append(Participant(id=str(uuid.uuid4()), side="mob", runtime=rt))
          enc.recompute_round()
          on_save()
          st.rerun()

  st.divider()
  st.markdown("### Participants actuels")
  if not enc.participants:
    st.caption("Aucun participant.")
    return

  for p in enc.participants:
    st.write({
      "id": p.id[:8],
      "side": p.side,
      "name": p.runtime.name,
      "HP": f"{p.runtime.hp:.1f}/{p.runtime.hp_max:.1f}",
      "MP": f"{p.runtime.mp:.1f}/{p.runtime.mp_max:.1f}",
      "STR": p.runtime.STR,
      "VIT": p.runtime.VIT,
    })

  c3, c4 = st.columns([1, 1])
  if c3.button("Reset encounter (vide)", key="btn_enc_reset"):
    enc.participants = []
    enc.turn_index = 0
    enc.recompute_round()
    enc.log = []
    on_save()
    st.rerun()

  if c4.button("Supprimer les morts (HP<=0)", key="btn_enc_prune_dead"):
    enc.participants = [pp for pp in enc.participants if pp.runtime.hp > 0]
    enc.recompute_round()
    on_save()
    st.rerun()


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


def render_action_panel(
  enc: EncounterState,
  comp: Compendium,
  vit_div: float,
  resolve_fn,
  on_save: Callable[[], None],
) -> None:
  actor = enc.current_actor()
  if actor is None:
    return

  targets = [p for p in enc.alive_participants() if p.id != actor.id]
  if not targets:
    st.warning("Aucune cible possible.")
    return

  labels = [f"{t.runtime.name} [{t.id[:6]}]" for t in targets]
  pick = st.selectbox("Cible", labels, key="target_pick")
  target = targets[labels.index(pick)]

  action_type = st.radio("Action", ["Attaque de base", "Skill"], horizontal=True, key="action_type")

  skill_name = None
  if action_type == "Skill":
    if not comp.skills:
      st.warning("Aucun skill importé.")
    else:
      skill_name = st.selectbox("Skill utilisé", sorted(comp.skills.keys()), key="skill_pick")
      s = comp.skills[skill_name]
      st.caption(f"Coût: {s.cost_mp or '—'} | Condition: {s.condition or '—'}")

  perce_armure = st.checkbox("Perce-armure (ignore VIT B dans dégâts)", value=False, key="perce_armure")

  c1, c2, c3 = st.columns([1, 1, 1])
  with c1:
    roll_a = st.number_input("Roll acteur (x)", min_value=0.0, max_value=10000.0, value=10.0, step=1.0, key="roll_a")
    if st.button("Random x", key="rand_x"):
      st.session_state["__tmp_rand_x"] = float(random.randint(1, 100))
      st.rerun()
    if "__tmp_rand_x" in st.session_state:
      roll_a = float(st.session_state.pop("__tmp_rand_x"))
      st.info(f"x généré: {roll_a}")

  with c2:
    roll_b = st.number_input("Roll cible (y)", min_value=0.0, max_value=10000.0, value=10.0, step=1.0, key="roll_b")
    if st.button("Random y", key="rand_y"):
      st.session_state["__tmp_rand_y"] = float(random.randint(1, 100))
      st.rerun()
    if "__tmp_rand_y" in st.session_state:
      roll_b = float(st.session_state.pop("__tmp_rand_y"))
      st.info(f"y généré: {roll_b}")

  with c3:
    st.write({"VIT divisor": vit_div})

  if st.button("Valider l'action (résoudre) ✅", type="primary", key="btn_resolve"):
    result = resolve_fn(
      attacker=actor.runtime,
      defender=target.runtime,
      roll_a=float(roll_a),
      roll_b=float(roll_b),
      perce_armure=bool(perce_armure),
      vit_scale_div=float(vit_div),
    )

    entry = ActionLogEntry(
      ts=time.time(),
      round=int(enc.round),
      turn_index=int(enc.turn_index),
      actor_id=actor.id,
      actor_name=actor.runtime.name,
      target_id=target.id,
      target_name=target.runtime.name,
      action_type="skill" if action_type == "Skill" else "basic_attack",
      skill_name=skill_name,
      roll_a=float(roll_a),
      roll_b=float(roll_b),
      perce_armure=bool(perce_armure),
      vit_div=float(vit_div),
      result=result,
    )
    enc.log.append(entry)
    enc.next_turn()
    on_save()

    st.success("Action enregistrée + tour avancé.")
    for line in result.get("effects", []):
      st.text(line)

    st.rerun()


# End of file