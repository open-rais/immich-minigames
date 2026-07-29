# Roadmap

Orden en el que se quiere construir el proyecto. Es un orden intencional elegido por el dueño del
proyecto (no solo un grafo de dependencias técnicas) - no reordenar sin confirmar primero.

Cuando se complete un item, marcar su checkbox.

- [X] 0. Documentar mejor `README.md`, `docs/GAMES/` y `docs/TODO/`
- [X] 1. Entender cómo funciona la BDD de Immich y el servicio de Immich-ML (Documentado en `docs/ARCHITECTURE/IMMICH.md`)
- [X] 2. Crear el CORE del proyecto
  - [X] 2.1. Obtener assets con condiciones (thumbnail, solo-foto, solo-video, aleatorio, por-ubicación, por-fecha, etc.)
  - [X] 2.2. Obtener personas con condiciones (thumbnail, solo-con-nombre, solo-con-fecha, por-cantidad-de-assets, por-nombre, etc.)
- [X] 3. API mínima para jugar MoreOrLess (solo modo `personAssets`)
- [X] 4. Frontend mínimo para jugar MoreOrLess
  - [X] 4.0. Configuración inicial de i18n permitiendo hacer traducciones
  - [X] 4.1. Frontend para PC en inglés
  - [X] 4.2. Frontend para móvil en inglés
  - [X] 4.3. Frontend traducido al español (Esto quedará para después)
  \*(Este patrón se repite para todos los frontends)
- [X] 5. Estructura base de frontend (menú que lista minijuegos + botón para comenzar un juego)
- [X] 6. API y frontend para Geoguessr (MapLibre GL JS con estilo similar a immich)
- [X] 7. API y frontend para Dateguessr
- [X] A. GHCR para poder levantarlo con docker-compose fácilmente. Usar github workflows
- [X] B. User login (Correo, username, nombre completo, password)
  - Diseño también debe ser consistente con immich.
  - Por ahora sólo lo básico: registrarse, iniciar sesión, cerrar sesión, página de perfil
- [X] C. Traducir a español
- [X] D. Agregar modo nocturno (consistente con immich, con su paleta de colores)
- [X] a. usar Claude Haiku para traducir la documentación a Inglés
- [X] b. Actualizar documentación a estado actual, además agregando cómo instalar/usar (env, docker-compose), que juegos están implementados, features que hay/no hay
- [X] 8. API y frontend para Immichdle (persondle)
- [X] 9. API y frontend para Who'sThatPerson
- [X] c. Opus code-review for smells, duplication, optimization, security
- [X] E. Aquí van las features de usuarios loggeados:
  - Mostrar records personales por juego (Ver implementación de albumes en immich, marcar el RP bajo al nombre del gamemode en menu principal, los daily tendrán el puntaje o un mensaje de "no jugado")
  - Página para editar usuario:
    - Cambiar username/nombre completo/skin
    - Se podrá seleccionar una persona de la librería de immich como "skin cosmetica"
      - Si puede ser repetido (Es cosmetico, no necesariamente será la persona del usuario)
      - En el header del menú, si hay una persona seleccionada, se mostrará esa cara en el círculo del usuario
- [X] F. Leaderboards:
  - Leaderboard por juego (Se puede ir a la ventana de leaderboard al ):
    - Será una tabla de top 15:
      - Se podrá ver historico/semanal/diario con la foto, nombre y puntaje
- [x] d. Actualizar documentación con Haiku
  - Mencionar en README.md que el proyecto está principalmente vibecodeado:
    - Recalcar que tengo un background en desarrollo de software, por lo que estoy haciendo auditoría constante + preocupandome en priorizar la seguridad de la instancia de immich al trabajar con Claude Code
  - Agregar un nuevo docs/INSTALL.md con distintas maneras de instalar el código o problemas comúnes
  - Actualizar otros archivos de documentación para cumplor con el estado actual
- [x] 10. Vista "Ver rounds": muestra cada asset mostrado en las rondas de un juego finalizado, con botón "ver en Immich"
- [x] e. Cambiar manera de guardar juegos antes de pasar a #G, para evitar que al actualizar la página se pierda el juego:
  - Hacer que al apretar un juego, en la ventana que dice "Jugar" o "leaderboard", si no hay ningún juego sin terminar asociado al jugador actual (ya sea loggeado o no) que la pantalla se vea igual. En caso de que haya una partida no terminada asociado aparecerá un botón extra "Continuar", si se presiona continuar se seguirá jugando el juego que ya estaba comenzado, el botón "Jugar" pasará a llamarse "Nuevo juego" y si se presiona ese, el juego anteriormente sin terminar se marca como terminado y se crea uno nuevo.
  - Agregar al perfil un botón de "ver juegos" en el que al presionarlo aparezca un modal con una targeta con una lista de los últimos 5 juegos del jugador con sesión iniciada, estos tendrán un link para ir a ver los rounds (#10).
- [x] f. Cambios a admin antes de pasar a daily:
  - [x] En lugar de tener una casilla "games" con todos los juegos, habrá una casilla para cada juego, y dentro estarán los modos así como ahora aparecen los juegos (implementado - los settings de cada juego también pasaron a ser por modo, no solo la UI)
  - [x] cada modo tendrá una casilla "Activar juego diario" para indicar que ese modo si estará en los daily (implementado junto con #G - ver `admin/AdminGameRow.tsx`'s "Juego diario" toggle)
  
- [x] G. Daily games (misma seed para cada usuario, solo se juega 1 vez al día, se puede ver la partida si ya se jugó, se puede compartir un link para invitar a jugar (Tipo wordle, etc)):
  - Se creará una nueva sección en menu principal, como si fuera un juego pero con el nombre "daily". Tendrá los mismos modos de juegos de abajo
  - Leaderboard de dailyGame (Se puede mover hacia atras en los días para ver los leaderboard de los dailies pasados)
  - El admin puede decir qué juegos están en el daily y cuales no, además de sus parámetros para el daily
  - Se podrá compartir un link a cada juego daily
  - No se debe repetir ningun asset/persona de los últimos N (default 30) días (excepto en more-or-less, ahi solo debe ser otra seed)
- [x] H. Cambio de sistema de usuarios (login obligatorio, invitaciones, reset de contraseña,
      rate limiting sesión-o-IP - ver `docs/TODO/NEW-AUTH.md`).
- [X] I. Agregar Logging (para auditoría).
- [ ] 11. API y frontend para Timeline
- [x] 12. MoreOrLess: nueva modalidad `album-asset-count`
- [ ] J. Code-Review humano completo.
  - Revisión completa del código
  - Búsqueda de optimizaciones
  - Limpieza de comentarios IA inutiles
  - Búsqueda de potenciales refactors, o des-refactorizaciones en caso de que la IA se haya sobre-complejizado:
    - en backend/src/games/, a cada juego, dividir game.py en game.py y round.py
    - games_service es muy grande:
      - Evaluar dividir en games (relacionado a juegos), score (relacionado a puntajes, leaderboard, etc) y daily (relacionado a creación de dailies y status) services
    - immich_service es muy largo
      - Ver si dividir en person/album/asset services
      - Evaluar otra opción de división lógica
    - en services/ está daily_settings, game_settings, game_registry.py y errors. No se si cuentan como services tal cual. Evaluar moverlos a otra parte:
      - Podría ser los settings y registry a games/ y errors a domain/
      - Evaluar por si hay otras maneras más lógicas
  - Refactorizar tests/:
    - Comenzar por pasar todo a subcarpetas ordenadas de manera lógica
    - Intentar dividir archivos grandes en más archivos pero más pequeños
- [ ] g. Config page:
  - En el header, hacer que ya no aparezcan los cambios de tema/idioma.
  - En su lugar, agregar otro botón más como los de arriba, para ir a página de configuración
  - Hacer los botónes consistentes con la recomendación de botónes para pantallas táctiles
  - En el panel de admin, poner las configuraciones de tema/idioma
    - Esto permite que después pueda haber más idiomas y se siga viendo con un buen UI/UX
    - Esto permite que después se pueda agregar una configuración de accesibilidad para reducir movimiento, que permita eliminar las animaciones de los juegos
- [ ] 13. MoreOrLess: nueva modalidad `person-birth-date` (probablemente sea muy fácil)
  - El juego no mostrará more/less en los botónes, ya que será esta persona nació antes/después. Eso serán los botónes (before/after, antes/después)
- [ ] 14. Immichdle: nueva modalidad `albumdle`
- [ ] 15. Admin Workers: Hacer que en el panel de admin haya un botón para procesar vectores de personas faltanes/reprocesar todos
  - Hacer que sea con workers
- [ ] h. Añadir script de desinstalación limpia (una manera segura de eliminar rastros de esta app, sin tocar nada de immich)
  - Si es posible y simple, que el script cree un snapshot de la db en caso de que después se quiera restaurar la app
    - En este caso, evaluar alguna de estas opciones
      - Crear un sistema de backup para toda la app (backups periodicos, manera de restaurar), de esta forma se aprovecha este sistema para volver a tener la app
      - Usar un script al inicio que restaure una instalación anterior
      - Otra opción
- [ ] i. Traducir al francés y alemán
<!-- 🎉 v1.0.0 🎉 -->
- [ ] K. Sistema de reporte
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
- [ ] 16. Agregar sistema de pistas a Immichdle
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
| **Script de desinstalación** | A | - | `backend/src/scripts/teardown_db_role.py`, simétrico a `bootstrap_db_role.py`: `DROP SCHEMA minigames CASCADE` + revoca los grants de `DB_APP_USERNAME` sobre `public` (incluye el `ALTER DEFAULT PRIVILEGES` que el bootstrap dejó ahí) + `DROP ROLE` - nunca toca datos ni objetos propios de Immich. Requiere confirmación explícita (`--yes`/dry-run), no debe correr automático como `db-init`. Pendiente decidir si también debe revertir el `REVOKE CREATE ON SCHEMA public FROM PUBLIC` del bootstrap - ese sí es un cambio al ACL del propio `public` de Immich, no algo scoped solo al rol de minigames.
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

## Copy-Paste de daily

```
# Por juego:
## MoL:
📈 racha: {N} 📉

## *guessr (0-39% rojo, 40%-79% amarillo, >80% verde):
🟩 4363 pts ({"2.4km"or"25 dias"})
🟨 2643 pts (*agregar distancia)
🟩 X pts (*agregar distancia)
🟥 340 pts (*agregar distancia)
🟨 X pts (*agregar distancia)
Total: N pts

## Immichdle:
🟩 adivinado en {N} intentos / 🟥 No fue adivinado
Total: N pts

## WTP:
🧑‍🧑‍🧒‍🧒 X/15 personas
Total: N pts

# Si se comparte total:
Todos resumidos a una linea
```