# Frontend Architecture

## Framework & Structure

Built with **Next.js** and **TypeScript**, using **App Router**.

```
frontend/
├── app/
│   ├── settings/
│   ├── games/
│   ├── more-or-less/
│   ├── geoguessr/
│   ├── dateguessr/
│   ├── who-is-there/
│   └── immichdle/
```

---

## Routing Structure

```
/
├── /settings                    # Connection settings
├── /games                       # Game selection
├── /more-or-less
│   ├── /person-items
│   ├── /album-items
│   └── /timeline
├── /geoguessr
├── /dateguessr
├── /who-is-there
└── /immichdle
```

---

## Key Architectural Decisions

1. **App Router** - Modern file-based routing
2. **Server Components** - Default for better performance
3. **TypeScript Strict Mode** - Type safety across the application
4. **Component Organization** - Feature-based directory structure
5. **API Routes** - Backend communication layer
