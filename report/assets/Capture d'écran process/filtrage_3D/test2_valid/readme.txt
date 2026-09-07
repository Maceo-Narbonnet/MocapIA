résultats du 20/10/2025

d'après le programme filtering.py et le Matlab P2SvsMoCap.m

-------------------------------------------------------------------------------------------------------------------------
###### filtering.py #####

[INPUT]

=> config.json qui contient les infos sur le filtrage à appliquer
=> fichier .trc/.csv des données des points 3D

[OUTPUT]

=> "person_0_filtering_report.pdf"
un pdf qui contient les courbes de l'évolution des coordonnées X,Y,Z de chaque keypoint filtrées et brut

=> un fichier CSV avec les données filtrées.

-------------------------------------------------------------------------------------------------------------------------
#####  P2SvsMoCap  #####

[INPUT]

=> les deux fichiers CSV filtré et brut

[OUTPUT]

=> MATLAB Figure qui contient les boxplots entre les données brutes et filtrées (capture d'écran équivalente)
=> capture d'écran "console"