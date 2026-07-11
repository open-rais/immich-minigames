# Geoguessr

## Inspiración

El juego online [GeoGuessr](https://www.geoguessr.com/): a partir de una imagen, adivinar en un
mapa dónde fue tomada.

## Cómo se juega

Se muestran entre 1 y 5 fotos que comparten ubicación (puede haber una diferencia menor de
distancia entre ellas). El jugador marca en un mapa dónde cree que fueron tomadas.

Se repite 5 veces, con fotos de ubicaciones distintas cada vez, y se suma el puntaje de las 5
rondas.

## Puntaje y fin de partida

- Al marcar, se mide la distancia entre el lugar real y el marcado.
- Acertar dentro de 1 km da el máximo: 5000 puntos. Más allá de eso, el puntaje va bajando a medida
  que la distancia marcada se aleja del lugar real (fórmula de decaimiento, sin ecuación exacta
  definida todavía).
- `hay_nuevo_round?`: hay ronda nueva mientras no se haya llegado a la 5ta ronda; en la 5ta, la
  partida termina.

## Modos

| Modo | Qué se pide adivinar | Prioridad |
|---|---|---|
| `distanceBetweenGuess` | Punto exacto en el mapa (puntaje por distancia) | Inicial |
| `country` | Solo el país | Futuro, última prioridad |
| `city` | Solo la ciudad | Futuro, última prioridad |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa cada modo futuro.
