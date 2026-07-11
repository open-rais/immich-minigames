# Dateguessr

## Inspiración

La misma mecánica de Geoguessr, pero cambiando "dónde" por "cuándo": en vez de un mapa, se usa una
línea de tiempo.

## Cómo se juega

Se muestra una foto y el jugador debe ubicarla en una línea de tiempo con forma de cinta métrica:
líneas grandes marcan años, medianas marcan meses, chicas marcan días. Haciendo scroll se acerca o
aleja (zoom) para poder ubicar el punto con precisión.

Se repite 5 veces, con fotos de fechas distintas cada vez, y se suma el puntaje de las 5 rondas.

## Puntaje y fin de partida

- Al marcar, se mide la distancia entre la fecha real y la marcada.
- Acertar la fecha exacta da el máximo: 5000 puntos. Más allá de eso, el puntaje va bajando a
  medida que la fecha marcada se aleja de la real (misma lógica de decaimiento que Geoguessr, sin
  ecuación exacta definida todavía).
- `hay_nuevo_round?`: hay ronda nueva mientras no se haya llegado a la 5ta ronda; en la 5ta, la
  partida termina.

## Modos

| Modo | Qué se pide adivinar | Prioridad |
|---|---|---|
| `daysToDate` | Fecha exacta (día) en la línea de tiempo | Inicial |
| `years` | Solo el año | Futuro, última prioridad |
| `months` | Solo el mes | Futuro, última prioridad |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa cada modo futuro.
