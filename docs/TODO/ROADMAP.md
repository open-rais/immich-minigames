# Roadmap

Orden en el que se quiere construir el proyecto. Es un orden intencional elegido por el dueño del
proyecto (no solo un grafo de dependencias técnicas) - no reordenar sin confirmar primero.

Cuando se complete un item, marcar su checkbox.

- [X] 0. Documentar mejor `README.md`, `docs/GAMES/` y `docs/TODO/`
- [X] 1. Entender cómo funciona la BDD de Immich y el servicio de Immich-ML (Documentado en `docs/ARCHITECTURE/IMMICH.md`)
<!-- v0.0.0 -->
- [X] 2. Crear el CORE del proyecto
  - [X] 2.1. Obtener assets con condiciones (thumbnail, solo-foto, solo-video, aleatorio, por-ubicación, por-fecha, etc.)
  - [X] 2.2. Obtener personas con condiciones (thumbnail, solo-con-nombre, solo-con-fecha, por-cantidad-de-assets, por-nombre, etc.)
<!-- v0.0.1 -->
- [X] 3. API mínima para jugar MoreOrLess (solo modo `personAssets`)
- [X] 4. Frontend mínimo para jugar MoreOrLess
  - [X] 4.0. Configuración inicial de i18n permitiendo hacer traducciones
  - [X] 4.1. Frontend para PC en inglés
  - [X] 4.2. Frontend para móvil en inglés
  - [X] 4.3. Frontend traducido al español (Esto quedará para después)
  \*(Este patrón se repite para todos los frontends)
<!-- v0.1.0 -->
- [X] 5. Estructura base de frontend (menú que lista minijuegos + botón para comenzar un juego)
<!-- v0.1.1 -->
- [X] 6. API y frontend para Geoguessr (MapLibre GL JS con estilo similar a immich)
<!-- v0.2.0 -->
- [X] 7. API y frontend para Dateguessr
<!-- v0.3.0 -->
<!-- Antes de pasar a #A-#b se hará un code review completo con Fable y code correction con Opus -->
- [X] A. GHCR para poder levantarlo con docker-compose fácilmente. Usar github workflows
- [X] B. User login (Correo, username, nombre completo, password)
  - Diseño también debe ser consistente con immich.
  - Por ahora sólo lo básico: registrarse, iniciar sesión, cerrar sesión, página de perfil
- [X] C. Traducir a español
- [X] D. Agregar modo nocturno (consistente con immich, con su paleta de colores)
- [X] a. usar Claude Haiku para traducir la documentación a Inglés
- [X] b. Actualizar documentación a estado actual, además agregando cómo instalar/usar (env, docker-compose), que juegos están implementados, features que hay/no hay
<!-- Publicar -->
- [X] 8. API y frontend para Immichdle (persondle)
<!-- v0.4.0 -->
- [X] 10. API y frontend para Who'sThatPerson
- [X] c. Opus code-review for smells, duplication, optimization, security
<!-- v0.5.0 -->
<!-- Aquí irá {Daily game} y {logged user features} -->
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
<!-- Crear nueva release -->
- [ ] G. Daily games (misma seed para cada usuario, solo se juega 1 vez al día):
  - Se creará una nueva sección en menu principal, como si fuera un juego pero con el nombre "daily". Tendrá los mismos modos de juegos de abajo
  - Leaderboard de dailyGame
- [ ] 9. API y frontend para Timeline
<!-- v0.6.0 -->
- [ ] 11. Agregar sistema de pistas a Immichdle
<!-- v0.7.0 -->
- [ ] 12. Vista "Ver rounds": muestra cada asset mostrado en las rondas de un juego finalizado, con botón "ver en Immich"
<!-- v0.7.1 -->
- [ ] 13. MoreOrLess: nueva modalidad `album-asset-count`
<!-- v0.8.0 -->
- [ ] 14. MoreOrLess: nueva modalidad `person-birth-date`
<!-- v0.8.1 -->
- [ ] 15. Immichdle: nueva modalidad `albumdle`
<!-- v0.8.2 -->
- [ ] 16. Geoguessr: nueva modalidad `Country`
<!-- v0.8.3 -->
- [ ] 17. Geoguessr: nueva modalidad `City`
<!-- v0.8.4 -->
- [ ] 18. Dateguessr: nueva modalidad `Year`
<!-- v0.8.5 -->
- [ ] 19. Dateguessr: nueva modalidad `Month`
<!-- v0.8.6 -->
- [ ] 20. Timeline: nueva modalidad `Level`
<!-- v0.8.7 -->

## Features condicionales (sin posición fija todavía)

Estas no tienen un número fijo en la lista de arriba porque su momento exacto depende de cómo vaya
avanzando el proyecto. Sí tienen restricciones de orden ya decididas:

| Feature | Debe ir después de | Debe ir antes de | Notas |
|---|---|---|---|
| **Redis** | 10 | - | Crucial para el proyecto, pero aún no entiendo cómo se usa ni cuales son sus casos de uso (soy principiante). Se prefiere ver el proyecto funcionando correctamente primero (al menos hasta el item 9) antes de meterlo. Nota: el caché simple en proceso de `get_immich_service()`/`Settings` (`functools.lru_cache`, sin estado compartido entre procesos) ya se resolvió en el punto 4 sin Redis - esta fila es sobre un caché real (compartido/distribuido), no sobre eso. | <!-- potencial v1.0.0 según lo demás que haya implementado -->
| **User login** | 7 | 15 | - | <!-- v0.+1.0 -->
| **Daily game** | 15 | - | Depende de tener login. Momento exacto sin definir, se decidirá según avance el proyecto. | <!-- v0.+1.0 -->
| **Report incorrect** | 11 | - | Agrega una tabla de reportes: no corrige metadata directamente, pero saca esos assets de los juegos y permite verlos en Immich para corregirlos ahí. Probablemente vaya después del 19 también, ya que no es el foco principal del proyecto. | 
| **Script de desinstalación** | A | - | `backend/src/scripts/teardown_db_role.py`, simétrico a `bootstrap_db_role.py`: `DROP SCHEMA minigames CASCADE` + revoca los grants de `DB_APP_USERNAME` sobre `public` (incluye el `ALTER DEFAULT PRIVILEGES` que el bootstrap dejó ahí) + `DROP ROLE` - nunca toca datos ni objetos propios de Immich. Requiere confirmación explícita (`--yes`/dry-run), no debe correr automático como `db-init`. Pendiente decidir si también debe revertir el `REVOKE CREATE ON SCHEMA public FROM PUBLIC` del bootstrap - ese sí es un cambio al ACL del propio `public` de Immich, no algo scoped solo al rol de minigames.

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
