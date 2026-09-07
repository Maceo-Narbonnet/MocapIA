28/10/2025

test avec le filtre butterworth + (ajout) KALMAN


!! SANS KALMAN !!

"kalman": {
      "to_do": false,
      "trust_ratio": 30,
      "smooth": false
      },


==> sans kalman notre filtre est bien mieux que celui de Matlab.


!! AVEC KALMAN !!

"kalman": {
      "to_do": true,
      "trust_ratio": 30,
      "smooth": false
      },

==> on s'éloigne un peu trop des mesures notamment dans les hautes fréquences (voir figure "aveckalman30")

==> plus on baisse le ratio, plus on s'éliogne du signal de base


==> au final le filtre kalman à ratio de 100 n'effectue pas énormément de changement sur le signal du LWrist mais autant le laisser.
Il faut faire la même comapraison sur le smallToe (voir les captures "..._SmallToe")

==> "smooth": true arrondi trop au niveau des hautes frqs