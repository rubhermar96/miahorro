// Every user-facing text lives here so the app can be translated later (RNF-03).
export const es = {
  app: { name: 'MiAhorro' },
  nav: {
    label: 'Navegación principal',
    home: 'Inicio',
    transactions: 'Movimientos',
    add: 'Añadir',
    plan: 'Planificar',
    more: 'Más',
  },
  home: {
    title: 'Inicio',
    netWorthTitle: 'Tu patrimonio',
    netWorthEmpty: 'Cuando añadas tus cuentas, aquí verás tu patrimonio neto y cómo evoluciona.',
  },
  transactions: { title: 'Movimientos' },
  add: { title: 'Añadir movimiento' },
  plan: { title: 'Planificar' },
  comingSoon: {
    title: 'Muy pronto',
    body: 'Esta sección llega en la iteración {{iteration}} del plan.',
  },
  more: {
    title: 'Más',
    appearance: 'Apariencia',
    theme: { label: 'Tema', system: 'Sistema', light: 'Claro', dark: 'Oscuro' },
    about: 'Acerca de',
    appVersion: 'Versión de la app',
    server: 'Servidor',
  },
  server: {
    checking: 'Comprobando conexión…',
    ok: 'Conectado · versión {{version}}',
    degraded: 'El servidor responde, pero la base de datos no está disponible',
    offline: 'Sin conexión con el servidor',
  },
  update: {
    available: 'Hay una versión nueva de MiAhorro.',
    reload: 'Actualizar',
    dismiss: 'Más tarde',
  },
  notFound: {
    title: 'Página no encontrada',
    back: 'Volver al inicio',
  },
}
