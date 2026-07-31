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
- [x] H. Cambio de sistema de usuarios (login obligatorio, invitaciones, reset de contraseña,
      rate limiting sesión-o-IP - ver `docs/TODO/NEW-AUTH.md`).
- [X] I. Agregar Logging (para auditoría).
- [x] 11. API y frontend para Timeline
- [x] 12. MoreOrLess: nueva modalidad `album-asset-count`
- [X] J. Code-Review completo
- [X] g. Config page
- [X] 13. MoreOrLess: nueva modalidad `person-birth-date` (probablemente jugarlo sea muy fácil, pero hacerlo igual)
  - El juego no mostrará more/less en los botónes, ya que será esta persona nació antes/después. Eso serán los botónes (before/after, antes/después)
- [x] 14. Immichdle: nueva modalidad `albumdle`
- [X] h. Arreglos de UI/UX
- [ ] K. En leaderboard de daily, al lado del nombre de cada persona, debería salir un badge indicando la racha de días seguidos que lleva el usuario completando el juego (da igual si pierde o no, solo de haber jugado el daily)
- [ ] i. Traducir al francés y alemán
<!-- 🎉 v1.0.0 🎉 -->
- [ ] j. Añadir script de desinstalación limpia (una manera segura de eliminar rastros de esta app, sin tocar nada de immich)
  - Si es posible y simple, que el script cree un snapshot de la db en caso de que después se quiera restaurar la app
    - En este caso, evaluar alguna de estas opciones
      - Crear un sistema de backup para toda la app (backups periodicos, manera de restaurar), de esta forma se aprovecha este sistema para volver a tener la app
      - Usar un script al inicio que restaure una instalación anterior
      - Otra opción
- [ ] 15. Admin Workers: Hacer que en el panel de admin haya un botón para procesar vectores de personas/albums faltanes/reprocesar todos
  - Hacer que sea con workers asincronos
- [ ] L. Sistema de reporte
  - En ver juego, en botón de ..., agregar un botón para reportar que abre un modal para enviar reporte
    - Si se reporta una persona, las opciones para seleccionar:
      - Fecha de nacimiento mala
      - Nombre y cara no hacen match
      - Nombre mal escrito
    - Si se reporta un album, las opciones para seleccionar
      - Portada y album no hacen match
      - Nombre mal escrito
    - Si se reporta un asset:
      - Ubicación mal ingresada
      - Fecha mal ingresada
      - Cara en asset no hace match
  - desde el panel de admin, agregar una opción para ir a la página de reportes:
    - 3 listas, 1 para cada tipo (asset, person, album)
    - cada lista con Infinite scroll
    - tendrá botón de ver en immich, además de botón para marcar como resuelto
  - En juegos que dependan de la fecha, excluir las reportadas con fecha mala
  - En juegos que dependan de fecha de nacimiento, excluir esas
  - ... así para cada reporte
  - Ojo que es para la generación de rondas solamente, pero igual si se debería poder intentar adivinar una persona mala (ej: en immichdle o who's that person si puedo buscar en el buscador aunque haya algo malo, solo que no debe poder ser una persona mala la que esté por adivinar)
  - Si alguien juega un daily y reporta, ese daily quedará con ese asset igualmente, aunque esté mal marcado
- [ ] M. PWA básica:
  - ícono de la app
  - Notificaciones:
    - 10:00 am: ya está disponible el nuevo daily
    - 9:00 pm: no has jugado el diario, puedes perder tu racha de {N}
  - Sin caché ni offline features aún
- [ ] 16. Agregar sistema de pistas a Immichdle (Reconsiderandolo, dado que ahora creo que está bien así como está)
- [ ] 17. Geoguessr: nueva modalidad `Country`
- [ ] 18. Geoguessr: nueva modalidad `City`
- [ ] 19. Dateguessr: nueva modalidad `Year`
- [ ] 20. Dateguessr: nueva modalidad `Month`
- [ ] 21. Timeline: nueva modalidad `Level`

## Features condicionales (sin posición fija todavía)

Estas no tienen un número fijo en la lista de arriba porque su momento exacto depende de cómo vaya
avanzando el proyecto. Sí tienen restricciones de orden ya decididas:

| Feature | Debe ir después de | Debe ir antes de | Notas |
|---|---|---|---|
| **Redis** | 10 | - | Crucial para el proyecto, pero aún no entiendo cómo se usa ni cuales son sus casos de uso (soy principiante). Se prefiere ver el proyecto funcionando correctamente primero (al menos hasta el item 9) antes de meterlo. Nota: el caché simple en proceso de `get_immich_service()`/`Settings` (`functools.lru_cache`, sin estado compartido entre procesos) ya se resolvió en el punto 4 sin Redis - esta fila es sobre un caché real (compartido/distribuido), no sobre eso. | <!-- potencial v1.0.0 según lo demás que haya implementado -->
| **Testing E2E de frontend (Playwright)** | e | - | Surgió al verificar el punto e: no había manera de comprobar visualmente el flujo Continuar/Nuevo juego sin instalar Playwright (headless Chromium) en el sandbox, y se decidió no instalarlo puntualmente para eso. Queda como tarea propia: agregar Playwright (`@playwright/test` o `pytest-playwright`) como dependencia de test E2E real, con specs versionados, corriendo en CI (github workflows, ver punto A). Momento exacto sin definir. |

## Limitaciones conocidas (menores, no bloquean nada)

- **MoreOrLess, animación de transición entre rondas**: el eje/distancia del deslizamiento
  (`frontend/src/games/MoreOrLess/MoreOrLessGame.tsx`) se calcula una sola vez al empezar la
  animación (~1.4-1.9s de punta a punta). Si en ese lapso cambia el breakpoint desktop/móvil -
  rotar el celular, redimensionar la ventana - la animación puede quedar con el eje viejo por esa
  única transición. Caso muy borde (ventana de tiempo corta, acción poco común mientras se está
  jugando); no se considera prioritario arreglarlo.

## Explícitamente fuera de este roadmap

**RepairMetadata** no tiene lugar en esta lista a propósito - es la prioridad más baja de todas,
un "quizás" a futuro, no una tarea planeada. Ya está anotada como tal en la sección "Extra
Features" de `README.md`; no se le asigna posición aquí ni se agrega a la tabla de condicionales.
