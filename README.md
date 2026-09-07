# MoCapIA — Stage TN09 (UTC, A25)

Stage effectué au sein du laboratoire (UMR 6600, plateforme motion capture) sur la capture de mouvement par IA : comparaison Vicon / GoPro / MoCapIA, calibration multi-caméras, triangulation et filtrage 3D, augmentation de marqueurs, intégration OpenSim.

## Contenu du dépôt

- `code/mocapia_2.0/` — Application MoCapIA (Python / PyQt).
  - `src/Camera/` — acquisition GoPro, calibration multi-caméras (damier), gestion du référentiel.
  - `src/Pose_Estimation/` — détection de pose (YOLO), triangulation, filtrage 3D.
  - `src/MarkerAugmenter/LSTM/` — augmentation de marqueurs (modèles ONNX `v0.3_upper` / `v0.3_lower`).
  - `src/Acc_Evaluation/` — évaluation de la précision face à la référence Vicon.
  - `src/Ui/` — interface PyQt (`MainWindow`).
- `report/` — Rapport de stage : projet LaTeX complet (`doc.tex`, `parts/`, `lib/`, `assets/`, `references.bib`) et PDF final `Rapport_FINAL_Maceo_NARBONNET.pdf`.
- `defense/final/` — Support de soutenance final (pptx / pdf) et ses ressources.
- `documentation/` — Production personnelle documentant le stage : `diagrams/` (schémas du pipeline), `paper-review-CR/` (compte-rendu d'article), `resume_bloc_OpenSim.pdf`.

## Poids YOLO (non versionnés)

Les poids pré-entraînés sont publics et deux d'entre eux dépassent la limite de 100 Mo de GitHub. Ils sont donc exclus du dépôt et doivent être placés dans `code/mocapia_2.0/src/` :

`yolov9e.pt`, `yolov9s.pt`, `yolo11x.pt`, `yolo11s.pt`, `yolo11s-pose.pt`

Ils se retéléchargent automatiquement via Ultralytics au premier usage, ou manuellement depuis les releases Ultralytics.

## Contenu conservé en local uniquement

Le dossier de stage complet contient d'autres éléments, volontairement hors dépôt (volume ou pertinence) :

| Élément | Raison |
| --- | --- |
| `experiments/` (~19 Go) | Runs bruts de l'application : vidéos GoPro, calibrations, captures, analyses. Très au-delà de ce que GitHub accepte. |
| `media/interviews/` (~570 Mo) | Enregistrements de l'interview MoCapIA du 14/10/2025. |
| `defense/colleagues-reports/` (~285 Mo) | Rapports et supports d'avancement des collègues du projet (Alexandru, Colin, Zhangyi). |
| `documentation/process-captures/` (~290 Mo) | Archive brute de toutes les captures d'écran du stage. Les images réellement utilisées sont dans `report/assets/`. |
| `research/` | Bibliographie externe et installeurs d'outils tiers (Kinovea, Cursor). |
| `admin/` | Convention de stage, évaluation, documents administratifs. |
| `archive/` | Anciennes versions de fichiers conservées par précaution. |
| `team-tea-time/` | Raccourcis Google Drive : des pointeurs, pas les fichiers réels. |

## Historique GitLab du code

`code/mocapia_2.0/` provient d'un dépôt GitLab du laboratoire (`gitlab.utc.fr/cebm/markerless/mocapia_3.git`, 102 commits). Son `.git` d'origine pèse 9 Go — il n'a pas été poussé ici mais conservé en local à côté du dossier de stage, sous `mocapia_2.0-gitlab-history.git`.
