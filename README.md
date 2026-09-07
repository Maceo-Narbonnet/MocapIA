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

