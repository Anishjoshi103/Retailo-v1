# Retailo frontend

Angular standalone application foundation. The initial screen is a placeholder workspace;
business workflows will be implemented in later milestones.

## Commands

```sh
npm install
npm start
npm test
npm run lint
npm run build
```

The app uses standalone components, Angular Router, strict TypeScript and signals for
local reactive state. Keep financial calculations and authorization decisions on the
backend; frontend display logic must not become the source of truth for GST or money.
