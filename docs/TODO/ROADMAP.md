# Roadmap

Orden en el que se quiere construir el proyecto. Es un orden intencional elegido por el dueño del
proyecto (no solo un grafo de dependencias técnicas) - no reordenar sin confirmar primero.

Cuando se complete un item, marcar su checkbox.

- [X] 0. Documentar mejor `README.md`, `docs/GAMES/` y `docs/TODO/`
- [X] 1. Entender cómo funciona la BDD de Immich y el servicio de Immich-ML (Documentado en `docs/ARCHITECTURE/IMMICH.md`)
- [X] 2. Crear el CORE del proyecto
- [X] 3. API mínima para jugar MoreOrLess (solo modo `personAssets`)
- [X] 4. Frontend mínimo para jugar MoreOrLess
- [X] 5. Estructura base de frontend (menú que lista minijuegos + botón para comenzar un juego)
- [X] 6. API y frontend para Geoguessr (MapLibre GL JS con estilo similar a immich)
- [X] 7. API y frontend para Dateguessr
- [X] A. GHCR para poder levantarlo con docker-compose fácilmente. Usar github workflows
- [X] B. User login (Correo, username, nombre completo, password)
- [X] C. Traducir a español
- [X] D. Agregar modo nocturno (consistente con immich, con su paleta de colores)
- [X] a. usar Claude Haiku para traducir la documentación a Inglés
- [X] b. Actualizar documentación a estado actual, además agregando cómo instalar/usar (env, docker-compose), que juegos están implementados, features que hay/no hay
- [X] 8. API y frontend para Immichdle (persondle)
- [X] 9. API y frontend para Who'sThatPerson
- [X] c. Opus code-review for smells, duplication, optimization, security
- [X] E. Aquí van las features de usuarios loggeados:
- [X] F. Leaderboards:
- [x] d. Actualizar documentación con Haiku
- [x] 10. Vista "Ver rounds": muestra cada asset mostrado en las rondas de un juego finalizado, con botón "ver en Immich"
- [x] e. Cambiar manera de guardar juegos antes de pasar a #G, para evitar que al actualizar la página se pierda el juego:
- [x] f. Cambios a admin antes de pasar a daily:
- [x] G. Daily games (misma seed para cada usuario, solo se juega 1 vez al día, se puede ver la partida si ya se jugó, se puede compartir un link para invitar a jugar (Tipo wordle, etc)):
- [x] H. Cambio de sistema de usuarios (login obligatorio, invitaciones, reset de contraseña, rate limiting sesión-o-IP).
- [X] I. Agregar Logging (para auditoría).
- [x] 11. API y frontend para Timeline
- [x] 12. MoreOrLess: nueva modalidad `album-asset-count`
- [X] J. Code-Review completo
- [X] g. Config page
- [X] 13. MoreOrLess: nueva modalidad `person-birth-date` (probablemente jugarlo sea muy fácil, pero hacerlo igual)
- [x] 14. Immichdle: nueva modalidad `albumdle`
- [X] h. Arreglos de UI/UX
- [X] K. En leaderboard de daily, al lado del nombre de cada persona, debería salir un badge indicando la racha de días seguidos que lleva el usuario completando el juego (da igual si pierde o no, solo de haber jugado el daily)
- [X] i. Traducir al francés y alemán
<!-- 🎉 v1.0.0 🎉 -->
- [X] L. Optimizar/Mejorar cargas con caché en frontend
- [X] M. Hacer testing automático para el frontend
- [x] 15. Admin Workers: Hacer que en el panel de admin haya un botón para procesar vectores de personas/albums faltanes/reprocesar todos
- [x] N. Sistema de reporte
- [X] O. PWA básica:
- [X] P. Juego Trivium.
- [ ] Q. Herramientas
  - [ ] Q.1. Personas similares:
    Selecciona una persona, se ordenará en una lista las personas más similares por promedio ML (Nombradas y no nombradas) con tal de poder "abrir en immich" y hacer merge
  - [ ] Q.2. Ubicaciones favoritas:
    - Marca en el mapa algunas ubicaciones que son comúnes o conocidas
    - O toca una foto que tenga ubicación y nombrala
  - [ ] Q.3. Sin ubicacion:
    - Ordena fotos que no tengan ubicación y permite seleccionar la ubicación guardada
    - \*Aún no está planeado cambiar la metadata, por ahora permitir copiar lat/log y "abrir en immich" para editar
  - [ ] Q.4. Parecido entre personas:
    Una vista que permite buscar personas y seleccionarlas, lo que crea una matriz de similitud entre las personas seleccionadas.
  - [ ] Q.5. (Experimental) Fecha incorrecta por cara:
    - Selecciona una persona que tenga muchas fotos (en distintos años)
    - Analiza el eje principal en que se mueve el vector entre las fotos antiguas y las nuevas, luego busca outliers (fotos que parezca tener otra edad) y ordena las fotos según qué tan alejado está del promedio que debería tener su cara a esa edad (deberían aparecer imagenes de fotos de cuando era niño, o fotos con fecha mal asignada)
- [ ] j. QoL Tips: Agregar un pequeño badge que aparezca de forma aleatoria al terminar algun juego
  - Aparece/No aparece de forma aleatoria, es decir, no aparecerá después de cada juego, aparecerá solo algunas veces. El mensaje que tendrá también será aleatorio
  - Mensajes que puede decir:
    - ¿Algún error en el juego? En "Ver Juego" puedes reportar un error.
    - ¿Quieres ver cómo te fue? Entra a "Clasificación".
    - Puedes revivir la partida en "Ver Juego".
    - Si quieres volver a ver este juego después, puedes ir a tu perfil y ver tus juegos pasados.
    - En "Ver juegos" puedes ver cada ronda y abrir cada uno en Immich.
    - \*Si es daily: Comparte los resultados por mensaje desde el botón de "Compartir". Si juegas todos los juegos diarios aparecerá un botón en el menú con un resumen de los resultados totales.
- [ ] k. QoL Nav: mejor navegación entre leaderboards:
  - Desde leaderboard de daily, en el título habrá "< Titulo >", y si toco las flechas me moveré entre los distintos juegos daily.
- [ ] l. QoL Nav: Mejor navegación entre dailies.
  - Si yo termino un juego daily, se abrirá un modal con los juegos daily que no he jugado
  - Si yo termino el último daily, se abrirá el modal de compartir todos los juegos por mensaje
- [ ] 16. Agregar sistema de pistas a Immichdle (Reconsiderandolo, dado que ahora creo que está bien así como está)
- [ ] 17. Geoguessr: nueva modalidad `Country` (Reconsiderandolo por el tema del reverse geo gratis)
- [ ] 18. Geoguessr: nueva modalidad `City`
- [ ] 19. Dateguessr: nueva modalidad `Year`
- [ ] 20. Dateguessr: nueva modalidad `Month`
- [ ] 21. Timeline: nueva modalidad `Level`

## Explícitamente fuera de este roadmap

**RepairMetadata** no tiene lugar en esta lista a propósito - es la prioridad más baja de todas,
un "quizás" a futuro, no una tarea planeada. Ya está anotada como tal en la sección "Extra
Features" de `README.md`; no se le asigna posición aquí ni se agrega a la tabla de condicionales.
