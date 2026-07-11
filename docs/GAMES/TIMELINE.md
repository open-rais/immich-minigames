# Timeline

## Inspiración

El juego de mesa ["Timeline"](https://en.wikipedia.org/wiki/Timeline_(card_game)): se van
insertando cartas de eventos en el orden cronológico correcto respecto a las cartas ya puestas en la
mesa.

## Cómo se juega

A diferencia de Dateguessr (que ubica una foto en un punto absoluto de una línea de tiempo), acá lo
que importa es el orden **relativo** entre fotos. Se entrega una foto inicial ya ubicada, luego se
entrega otra foto y el jugador debe insertarla en la posición correcta respecto a las fotos que ya
están en la línea de tiempo.

- **arcade** (modo inicial): se parte con una foto, se pasa otra; si se ubica bien, se pasa otra más
  (y así sucesivamente); al fallar, termina la partida.
- **Level** (modo futuro): se entregan N fotos de una vez y hay que ordenarlas todas correctamente.

## Puntaje y fin de partida

Pendiente de definir con precisión - todavía no hay docstring de `TimelineGame`/`TimelineRound` en
`games/timeline.py`. Lo que sí está claro del modo arcade: acertar continúa la racha, fallar termina
la partida (mismo patrón que MoreOrLess). La fórmula exacta de puntaje (¿puntos fijos por acierto?
¿depende de cuántas fotos ya había en la línea?) queda por decidir antes de implementar este juego.

## Modos

| Modo | Prioridad |
|---|---|
| `arcade` | Inicial |
| `Level` | Futuro, ver roadmap |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa el modo `Level`.
