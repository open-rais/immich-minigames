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
- [ ] 4. Frontend mínimo para jugar MoreOrLess
  - [X] 4.0. Configuración inicial de i18n permitiendo hacer traducciones
  - [X] 4.1. Frontend para PC en inglés
  - [X] 4.2. Frontend para móvil en inglés
  - [ ] 4.3. Frontend traducido al español (Esto quedará para después)
  \*(Este patrón se repite para todos los frontends)
<!-- v0.1.0 -->
- [ ] 5. Estructura base de frontend (menú que lista minijuegos + botón para comenzar un juego)
<!-- v0.1.1 -->
- [ ] 6. API y frontend para Geoguessr (MapLibre GL JS con estilo similar a immich)
<!-- v0.2.0 -->
- [ ] 7. API y frontend para Dateguessr
<!-- v0.3.0 -->
- [ ] 8. API y frontend para Immichdle (persondle)
<!-- v0.4.0 -->
- [ ] 9. API y frontend para Timeline
<!-- v0.5.0 -->
- [ ] 10. API y frontend para Who'sThatPerson
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
| **Report incorrect** | 11 | - | Agrega una tabla de reportes: no corrige metadata directamente, pero saca esos assets de los juegos y permite verlos en Immich para corregirlos ahí. Probablemente vaya después del 19 también, ya que no es el foco principal del proyecto. | <!-- v0.+1.0 -->
| **GHCR** | 5 | - | Distinto para tags vX.Y.Z y para último commit en main.
| **Modo oscuro** | 5 | - | Usar paleta de colores de Immich.

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
