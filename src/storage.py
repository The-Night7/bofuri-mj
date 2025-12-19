import json
from pathlib import Path
from typing import List, Dict, Any

from .models import Entity


DATA_DIR = Path("data")
ENTITIES_PATH = DATA_DIR / "entities.json"
SETTINGS_PATH = DATA_DIR / "settings.json"


def _ensure_data_dir() -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
  _ensure_data_dir()
  if not SETTINGS_PATH.exists():
    SETTINGS_PATH.write_text(json.dumps({"vit_divisor": 100.0}, ensure_ascii=False, indent=2), encoding="utf-8")
  return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(settings: Dict[str, Any]) -> None:
  _ensure_data_dir()
  SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def load_entities() -> List[Entity]:
  _ensure_data_dir()
  if not ENTITIES_PATH.exists():
    ENTITIES_PATH.write_text(json.dumps({"entities": []}, ensure_ascii=False, indent=2), encoding="utf-8")
  raw = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
  entities = [Entity.from_dict(e) for e in raw.get("entities", [])]
  return entities


def save_entities(entities: List[Entity]) -> None:
  _ensure_data_dir()
  payload = {"entities": [e.to_dict() for e in entities]}
  ENTITIES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
