# Assistant MJ — Bofuri RP (V2)

## Lancer
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Import docs/
1) Mets tes fichiers `.md` dans `docs/` (ex: `docs/Bestiaire.md`, `docs/tout.md`)
2) Dans l’app → onglet **Import & Admin** → **Importer docs/**
3) Ça génère `data/compendium.json`

## Notes parsing
- Le parser du bestiaire cherche des sections du type :
  - `### **Nom** (Lvl 1-10)` puis blocs `**Niveau 1:**` avec lignes `- **HP:** 10/10` etc.
- Les compétences sont lues sous `- **Compétences:**` puis des lignes listées.
- Les skills sont lus depuis `tout.md` (priorité) ou `palierX.md` si `tout.md` absent.

## Persistant vs non-persistant
- Les PJ (players.json) gardent leurs PV/PM d’une session à l’autre (si tu sauvegardes).
- Les monstres sont recréés à partir du compendium à chaque résolution (PV/PM "fresh" par défaut).

Prochaine V3 possible :
- gestion d’Encounter (PV/PM monstres persistants pendant le combat)
- boutons "utiliser compétence" (poison/tour, invocations, etc.) avec statuts et durée
- import armures/objets/xp
