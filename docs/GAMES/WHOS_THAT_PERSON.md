# Who'sThatPerson

## Inspiración

El segmento ["Who's That Pokémon?"](https://pokemon.fandom.com/wiki/Who's_That_Pok%C3%A9mon%3F)
del anime de Pokémon: se muestra una silueta y hay que adivinar de quién se trata antes de que se
revele.

## Cómo se juega

Se muestra una foto con una o más personas. Los rectángulos donde están las caras (detectadas por
el reconocimiento facial de Immich) se tapan con un cuadro negro. El jugador hace click en uno de
esos cuadros y escribe el nombre de la persona que cree que está ahí.

- Máximo 5 caras tapadas por foto.
- Se van mostrando fotos nuevas hasta **preguntar por 15 personas en total** (15 rondas), sin
  importar si se acierta o no - una partida puede terminar con entre 0/15 y 15/15 aciertos.

## Puntaje y fin de partida

- `has_next_round()`: hay ronda nueva mientras no se haya preguntado por la 15ª persona
  (`round_index < 15`); en la 15ª, la partida termina.
- `calculate_score()`: puntaje acumulado tipo combo - cada acierto suma el valor de la racha actual
  (que crece con cada acierto consecutivo, partiendo en 1); un fallo resetea la racha a 0 y no suma
  puntos en esa ronda (pero no resta lo ya ganado en rondas previas). Ejemplo con 6 rondas
  acierto-acierto-acierto-fallo-acierto-acierto: +1, +2, +3, +0, +1, +2 → puntaje final 9.
