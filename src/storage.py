import json
from pathlib import Path
from typing import List, Dict, Any

from .models import Player, Compendium


DATA_DIR = Path("data")
PLAYERS_PATH = DATA_DIR / "players.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
COMPENDIUM_PATH = DATA_DIR / "compendium.json"


def _ensure_data_dir() -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
  _ensure_data_dir()
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
  _ensure_data_dir()
  SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def load_players() -> List[Player]:
  _ensure_data_dir()
  if not PLAYERS_PATH.exists():
    PLAYERS_PATH.write_text(json.dumps({"players": []}, ensure_ascii=False, indent=2), encoding="utf-8")
  raw = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))
  return [Player.from_dict(p) for p in raw.get("players", [])]


def save_players(players: List[Player]) -> None:
  _ensure_data_dir()
  payload = {"players": [p.to_dict() for p in players]}
  PLAYERS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_compendium(path: str | None = None) -> Compendium:
  _ensure_data_dir()
  p = Path(path) if path else COMPENDIUM_PATH
  if not p.exists():
    # compendium vide par défaut
    return Compendium(monsters={}, skills={})
  raw = json.loads(p.read_text(encoding="utf-8"))
  return Compendium.from_dict(raw)


def save_compendium(compendium: Compendium, path: str | None = None) -> None:
  _ensure_data_dir()
  p = Path(path) if path else COMPENDIUM_PATH
  p.write_text(json.dumps(compendium.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
