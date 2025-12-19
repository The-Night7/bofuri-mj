# Assistant MJ — Bofuri RP

## Lancer
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Données
- `data/entities.json` : base des entités (PJ / Mob / Boss)
- `data/settings.json` : paramètres globaux (diviseur VIT par défaut)

## Notes
- L’app sauvegarde les PV/PM actuels si tu cliques sur "Sauvegarder".
- Tu peux reset PV/PM pour tout le monde via le bouton dédié.

## Prochaines évolutions possibles
- Import auto depuis tes .md (bestiaire/skills/objets/armures)
- Statuts (poison, brûlure, immobilisation), durées
- Coût MP, cooldowns, multi-hits
- XP automatique selon ton tableau
