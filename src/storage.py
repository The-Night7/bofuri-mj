import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import Player, Compendium, EncounterState


DATA_DIR = Path("data")
PLAYERS_PATH = DATA_DIR / "players.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
COMPENDIUM_PATH = DATA_DIR / "compendium.json"
ENCOUNTERS_DIR = DATA_DIR / "encounters"


def _ensure_dirs() -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  ENCOUNTERS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
  _ensure_dirs()
  if not SETTINGS_PATH.exists():
    SETTINGS_PATH.write_text(
      json.dumps(
        {"vit_divisor_default": 100.0, "docs_dir": "docs", "compendium_path": "data/compendium.json"},
        ensure_ascii=False, indent=2
      ),
      encoding="utf-8"
    )
  return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(settings: Dict[str, Any]) -> None:
  _ensure_dirs()
  SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def load_players() -> List[Player]:
  _ensure_dirs()
  if not PLAYERS_PATH.exists():
    PLAYERS_PATH.write_text(json.dumps({"players": []}, ensure_ascii=False, indent=2), encoding="utf-8")
  raw = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))
  return [Player.from_dict(p) for p in raw.get("players", [])]


def save_players(players: List[Player]) -> None:
  _ensure_dirs()
  payload = {"players": [p.to_dict() for p in players]}
  PLAYERS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_compendium(path: Optional[str] = None) -> Compendium:
  _ensure_dirs()
  p = Path(path) if path else COMPENDIUM_PATH
  if not p.exists():
    return Compendium(monsters={}, skills={})
  raw = json.loads(p.read_text(encoding="utf-8"))
  return Compendium.from_dict(raw)


def save_compendium(compendium: Compendium, path: Optional[str] = None) -> None:
  _ensure_dirs()
  p = Path(path) if path else COMPENDIUM_PATH
  p.write_text(json.dumps(compendium.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- Encounter persistence ----------------

def encounter_path(encounter_id: str) -> Path:
  _ensure_dirs()
  return ENCOUNTERS_DIR / f"{encounter_id}.json"


def save_encounter(state: EncounterState) -> None:
  p = encounter_path(state.encounter_id)
  p.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_encounter(encounter_id: str) -> EncounterState:
  p = encounter_path(encounter_id)
  raw = json.loads(p.read_text(encoding="utf-8"))
  return EncounterState.from_dict(raw)


def list_encounters() -> List[str]:
  _ensure_dirs()
  return sorted([x.stem for x in ENCOUNTERS_DIR.glob("*.json")])
