# Frontend Development Guide

## Estructura del Proyecto

```
frontend/
├── app/                    # Páginas principales (App Router)
│   ├── page.tsx           # Página de inicio (home)
│   ├── layout.tsx         # Layout raíz
│   ├── settings/          # Página de configuración
│   ├── games/             # Selector de juegos
│   └── more-or-less/      # Juego More or Less
├── components/            # Componentes React reutilizables
│   ├── GameLayout.tsx     # Layout para juegos
│   └── ui.tsx             # Componentes UI base
├── lib/                   # Lógica y utilidades
│   ├── api-client.ts      # Cliente HTTP para el backend
│   ├── storage.ts         # Manejo de localStorage
│   ├── utils.ts           # Funciones utilitarias
│   └── hooks.ts           # Custom React hooks
├── types/                 # TypeScript types y interfaces
│   └── api.ts             # Tipos de API
└── styles/               # Estilos globales
    └── globals.css       # Estilos Tailwind CSS
```

## Componentes Disponibles

### UI Components (`components/ui.tsx`)

- **Button** - Botón reutilizable con variantes
- **Card** - Componente tarjeta
- **Input** - Input con label y validación
- **Alert** - Alertas de error, éxito, info
- **LoadingSpinner** - Indicador de carga

### GameLayout (`components/GameLayout.tsx`)

Layout especializado para juegos con:
- Header con título y botón de atrás
- Link a settings en la esquina
- Estilo consistente con gradiente

## API Client

El cliente API (`lib/api-client.ts`) proporciona métodos para:

- **Settings**: `getSettings()`, `updateSettings()`, `testImmichConnection()`
- **Games**: `getAvailableGames()`
- **Sessions**: `createSession()`, `getSession()`, `completeSession()`
- **Rounds**: `getNextRound()`, `submitGuess()`
- **Stats**: `getGameStats()`, `getSessionStats()`
- **Health**: `checkHealth()`

## Hooks Personalizados

### useApi

Hook para manejar estados de carga y error en llamadas API:

```typescript
const { data, loading, error, execute } = useApi<GameInfo[]>({
  onSuccess: () => console.log('Success!'),
  onError: (err) => console.error(err),
});

// Usar:
const games = await execute(() => apiClient.getAvailableGames());
```

## Local Storage

La utilidad `storage` gestiona el estado del cliente:

```typescript
import { storage } from '@/lib/storage';

// Session Management
storage.setCurrentSessionId(id);
storage.getCurrentSessionId();
storage.clearCurrentSessionId();

// Settings
storage.setSettingsConfigured(true);
storage.isSettingsConfigured();

// Preferences
storage.setPreferences({ theme: 'dark' });
storage.getPreferences();
```

## Utilidades

Funciones helpers en `lib/utils.ts`:

- `cn()` - Combine class names
- `formatNumber()` - Formatea números
- `formatDate()` - Formatea fechas
- `formatTime()` - Formatea tiempos
- `debounce()` - Debounce para funciones

## Desarrollo

### Instalar dependencias

```bash
cd frontend
npm install
```

### Ejecutar servidor de desarrollo

```bash
npm run dev
```

La aplicación estará disponible en `http://localhost:3000`

### Compilar para producción

```bash
npm run build
npm start
```

### Linting

```bash
npm run lint
```

### Formatear código

```bash
npm run format  # Si tienes un script de prettier configurado
```

## Variables de Entorno

El archivo `.env.local` contiene:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Environment
NODE_ENV=development
```

Para producción, actualiza `NEXT_PUBLIC_API_URL` a la URL del backend en el servidor.

## Flujo de Navegación

```
/ (Home)
├── /settings (Configurar Immich)
├── /games (Selector de juegos)
│   ├── /more-or-less (Juego)
│   ├── /geoguessr (Juego)
│   ├── /dateguessr (Juego)
│   ├── /who-is-there (Juego)
│   └── /immichdle (Juego)
```

## Agregar Nuevos Juegos

1. Crear directorio: `app/[game-name]/`
2. Crear `app/[game-name]/page.tsx`
3. Importar `GameLayout` como wrapper
4. Usar `apiClient.createSession()` para iniciar sesión
5. Usar `apiClient.getNextRound()` para obtener datos
6. Usar `apiClient.submitGuess()` para enviar respuestas

## Estilo y Diseño

- **Framework**: Tailwind CSS v4
- **Paleta**: Blue como color primario
- **Dark Mode**: Soporte completo con `dark:` classes
- **Responsive**: Mobile-first design

## Pasos Siguientes

1. Configurar la URL del backend en `.env.local`
2. Asegurar que el backend está corriendo
3. Ejecutar `npm run dev`
4. Ir a http://localhost:3000 y configurar Immich
5. Empezar a jugar!

## Troubleshooting

**Backend no responde:**
- Verifica que `NEXT_PUBLIC_API_URL` es correcto
- Asegúrate que el backend está corriendo en http://localhost:8000

**Errores de TypeScript:**
- Ejecuta `npm run lint` para ver los errores
- Asegúrate que los tipos están importados correctamente

**Estilos no se aplican:**
- Verifica que Tailwind CSS está compilado correctamente
- Limpia `.next/` y vuelve a compilar: `npm run build`

## Recursos

- [Next.js Docs](https://nextjs.org/docs)
- [TypeScript React Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
