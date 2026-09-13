# apps/mobile — THALI × P.L.A.T.E. Universal Mobile Application

**GATE 02B — boundary only. No screens, auth, navigation, or workflows are
implemented.**

## Purpose

Universal role-aware mobile application. Role switching within one binary:

- **THALI**: Patient + Caregiver experience (logging, portion confirm).
- **P.L.A.T.E.**: Care-team mobile experience (Doctor, Nurse, Care
  Coordinator, Dietitian/Diabetes Educator, Field Health Worker).

## Approved technology stack (frozen — do not substitute)

- React Native + Expo
- Expo Router (navigation)
- Zustand (client state)
- TanStack Query (server state)
- React Hook Form + Zod (forms/validation)
- Expo SQLite (on-device store)
- SQLCipher (encryption)
- Drizzle ORM (type-safe schema)

## Dependencies

Recorded below for the scaffold. **Nothing is installed at Gate 02B** — no
`npm install`, no `npx expo`, no lockfile. Installation happens in the app
bootstrap gate.

```
react-native  expo  expo-router  zustand  @tanstack/react-query
react-hook-form  zod  expo-sqlite  sqlcipher  drizzle-orm
```

## Deferred (later gates)

- Expo project initialization (`package.json`, `app.json`, entry files)
- Authentication / onboarding
- Navigation wiring
- Patient & caregiver logging workflows
- Clinician workflows
- Local SQLite schema + sync engine

## Boundary rule

`apps/mobile` communicates with the backend exclusively through the published
API; it never reaches into `app/*` legacy internals.