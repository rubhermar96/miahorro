# MiAhorro: plan de desarrollo del MVP

> **Estado:** v1.0 · 14/10/2026 · Basado en [requisitos.md](requisitos.md) v1.0. Todavía sin código.

---

## 1. Cómo vamos a trabajar

- **12 iteraciones (de la 0 a la 11).** Cada una es una porción vertical completa (base de datos → API → pantalla) que termina **desplegada en `https://miahorro.octogas.es`** y que puedes usar.
- **Cierre de cada iteración:** demo, tu prueba en el iPhone con la lista de aceptación y, solo si das el visto bueno, pasamos a la siguiente.
- **Uso real desde la iteración 2.** Los datos que metas se conservan: las migraciones de la base de datos y las copias de seguridad existen desde la iteración 0.
- **Cambios de alcance:** primero se actualiza `requisitos.md` y después este plan.
- **Sin fechas.** El ritmo depende de tu disponibilidad, así que cada iteración lleva un tamaño relativo: **S** (pequeña), **M** (media) o **L** (grande).

---

## 2. Definición de terminado (vale para todas las iteraciones)

Una iteración está terminada cuando:

1. Todos los tests pasan en la integración continua.
2. Los cálculos financieros nuevos tienen tests con casos verificados (RNF-10).
3. Cada endpoint nuevo tiene su test de aislamiento: otro usuario no puede leer ni modificar esos datos (RF-PLT-01).
4. Los importes usan `Decimal` de principio a fin; nunca coma flotante (RNF-04).
5. Las migraciones de base de datos se aplican y se revierten sin errores.
6. Está desplegada en producción y octogas.es sigue funcionando igual (RNF-18).
7. Has pasado la lista de aceptación en tu iPhone.
8. Ningún log contiene datos financieros (RNF-15).

---

## 3. Estrategia de pruebas

| Nivel | Herramienta | Qué cubre | Cuándo se ejecuta |
|---|---|---|---|
| Cálculos financieros | pytest + Hypothesis | Amortización, intereses, FIFO, calculadoras: casos verificados (simuladores de bancos, Excel, cuadros reales) y propiedades que siempre deben cumplirse (p. ej. la suma de amortizaciones es igual al capital) | En cada cambio |
| API | pytest + cliente de pruebas de FastAPI + PostgreSQL real en Docker | Endpoints, permisos, aislamiento entre usuarios, migraciones | En cada cambio |
| Componentes del frontend | Vitest + Testing Library | Pantallas con lógica: alta rápida, mapeo de importación, presupuestos | En cada cambio |
| Extremo a extremo | Playwright con motor WebKit (el de Safari) y pantalla de iPhone | Flujos críticos: entrar, apuntar un gasto, importar un extracto, presupuestar | En cada cambio |
| Aceptación | Tu iPhone, con una lista por iteración | Lo que no se puede automatizar: instalar la PWA, Face ID, Apple Pay, sensación de uso | Al cerrar cada iteración |

La integración continua ejecuta todo menos la aceptación manual en cada `push`.

---

## 4. Mapa de iteraciones

| # | Iteración | Al terminar podrás… | Tamaño | Depende de |
|---|---|---|---|---|
| 0 | Cimientos y despliegue | Instalar la app vacía en el iPhone desde `miahorro.octogas.es` | M | — |
| 1 | Acceso seguro | Entrar con Face ID (passkey) o con contraseña y segundo factor | M | 0 |
| 2 | Cuentas y movimientos | Registrar tus cuentas y apuntar gastos en 3 toques | L | 1 |
| 3 | Importación y reglas | Cargar los extractos de Bankinter y Cajamar ya categorizados | L | 2 |
| 4 | Apple Pay y conciliación | Ver cada pago con el iPhone al instante, sin duplicados al importar | M | 3 |
| 5 | Objetivos de ahorro | Seguir tus objetivos y tu tasa de ahorro | M | 2 |
| 6 | Presupuestos | Presupuestar con límites o en base cero | L | 5 |
| 7 | Préstamos | Ver el cuadro de amortización real y simular amortizar | M | 2 |
| 8 | Calculadoras | Simular vivienda, hipoteca, coche, préstamos y ahorro | L | 7 |
| 9 | Inversiones | Llevar tu cartera con plusvalías FIFO | L | 2 |
| 10 | Panel e informes | Ver tu patrimonio neto, su evolución y en qué gastas | M | 4–9 |
| 11 | Cierre del MVP | Usarla a diario con garantías de rendimiento, seguridad y recuperación | M | 10 |

Las iteraciones 5–9 dependen sobre todo de la 2. Si alguna te corre más prisa (por ejemplo, las calculadoras), se puede adelantar.

---

## 5. Detalle de las iteraciones

### Iteración 0 · Cimientos y despliegue (M)

**Objetivo:** montar el esqueleto completo y publicarlo antes de construir funcionalidades, para descubrir pronto cualquier problema de la VPS compartida.

**Entregables**
- Repositorio Git con esta estructura:
  - `backend/`: API con FastAPI.
  - `backend/finance/`: paquete de cálculos financieros, sin dependencias de FastAPI.
  - `frontend/`: React + TypeScript + Vite.
  - `deploy/`: Docker Compose, configuración del proxy y scripts de copias.
  - `docs/`.
- Calidad automática: formateo y linters (Ruff, ESLint, Prettier), comprobación de tipos en Python y TypeScript, ganchos antes de cada commit e integración continua.
- Backend: configuración por variables de entorno, PostgreSQL con Alembic, endpoint de salud, errores con formato uniforme y logs sin datos financieros.
- Frontend:
  - PWA instalable: manifiesto, iconos y *service worker*.
  - Diseño *mobile-first* con navegación inferior y tema claro/oscuro.
  - Formatos es-ES y textos preparados para traducción.
  - Cliente de la API generado automáticamente desde OpenAPI.
- Entorno local con Docker Compose que replica producción.
- Producción:
  - Registro DNS y host virtual en el proxy de octogas.es, con HTTPS.
  - Contenedores con límites de memoria y CPU, red y base de datos propias.
- Copias: volcado diario cifrado de la base de datos a almacenamiento externo, con 30 días de retención, y script de restauración.

**Requisitos:** RNF-01, 02 (base), 03, 05 (HTTPS), 06, 07, 09, 14–18 · RF-IMP-05.

**Cómo probarlo**
- *Automático:* integración continua en verde; test de salud; la API se niega a arrancar si falta configuración obligatoria.
- *Aceptación:*
  - [ ] Abrir `https://miahorro.octogas.es` en Safari, añadirla a la pantalla de inicio y que se abra a pantalla completa.
  - [ ] octogas.es responde igual antes y después del despliegue, con su certificado intacto.
  - [ ] Simulacro: borrar la base de datos de producción (aún vacía) y restaurarla desde la copia externa.
  - [ ] Consumo de memoria medido y dentro de los límites.

**Necesito de ti:** el registro DNS en DonDominio, saber qué proxy usa octogas.es y un almacenamiento externo gratuito para las copias (ver §8).

---

### Iteración 1 · Acceso seguro y multiusuario (M)

**Objetivo:** que solo tú puedas entrar, de forma cómoda y segura, y dejar establecido el patrón que aísla los datos de cada usuario.

**Entregables**
- Contraseña con Argon2, segundo factor TOTP con códigos de recuperación y passkeys (Face ID).
- Sesión en cookie `__Host-`, `HttpOnly`, `Secure` y `SameSite`; protección CSRF; bloqueo tras intentos fallidos; cerrar sesión en todos los dispositivos.
- Pantalla de registro abierta (D22): el primer usuario registrado es el administrador; tope de usuarios e interruptor para cerrar el registro. Comandos de consola para gestionar usuarios.
- Patrón de aislamiento: cada dato pertenece a un usuario y el filtro se aplica en una única capa. Incluye un test genérico que intenta acceder con otro usuario a cada endpoint.
- Panel `/admin` (SQLAdmin) solo para administradores, con la gestión de usuarios y la estructura de las tablas de referencia.
- Preferencias: divisa, día de inicio del mes financiero, tema e idioma.

**Requisitos:** RF-USR-01, RF-USR-04, RF-PLT-01, RF-PLT-02 (estructura), RF-PLT-03 · RNF-05.

**Cómo probarlo**
- *Automático:* contraseña, TOTP, passkey con autenticador simulado, bloqueo, caducidad de sesión, atributos de la cookie, CSRF y aislamiento.
- *Aceptación:*
  - [ ] Registrar una passkey con Face ID y entrar con ella desde la app instalada.
  - [ ] Entrar con contraseña y código desde el ordenador.
  - [ ] Cinco contraseñas erróneas bloquean temporalmente el acceso.
  - [ ] Un usuario de prueba sin permisos no puede entrar en `/admin`.

---

### Iteración 2 · Cuentas y movimientos (L)

**Objetivo:** empezar a usar MiAhorro de verdad apuntando a mano.

**Entregables**
- Entidades y cuentas de todos los tipos, con saldo inicial y archivado.
- Remuneración por tramos, liquidación, retención e histórico de tipos (solo configuración; el cálculo de intereses es F2).
- Depósitos a plazo con vencimiento, renovación y penalización, y lista de próximos vencimientos.
- Categorías jerárquicas con un conjunto inicial adaptado a España, etiquetas y notas.
- **Alta rápida en 3 toques:** teclado numérico, última cuenta usada y categorías frecuentes.
- Transferencias manuales entre cuentas propias.
- Lista de movimientos con búsqueda y filtros.
- Conciliación de saldo con movimiento de ajuste.
- Inicio provisional con el saldo de cada cuenta y el total.

**Requisitos:** RF-CTA-01, 02, 03, 04, 07, 08 · RF-MOV-01, 02, 03, 04 (parte manual), 15 (búsqueda y filtros) · RNF-04.

**Cómo probarlo**
- *Automático:* el saldo es siempre el saldo inicial más los movimientos; las transferencias no cuentan como ingreso ni gasto; se rechazan importes en coma flotante; aislamiento.
- *Extremo a extremo:* crear una cuenta, apuntar un gasto en 3 toques y verlo en la lista y en el saldo.
- *Aceptación:*
  - [ ] Apuntar tus gastos reales durante unos días.
  - [ ] El saldo de cada cuenta cuadra con el de Bankinter y Cajamar.
  - [ ] El alta rápida se hace cómodamente con una mano.

---

### Iteración 3 · Importación de extractos y reglas (L)

**Objetivo:** que la mayoría de movimientos bancarios entren con una importación y salgan ya categorizados.

**Entregables**
- Importador CSV/XLSX:
  - Detecta la codificación, el separador y los formatos españoles de fecha e importe (`1.234,56`).
  - Asistente de mapeo de columnas y vista previa antes de confirmar.
  - Lo configurado se guarda como plantilla compartida.
- Plantillas de **Bankinter y Cajamar**: en PDF, el extracto mensual que genera el banco, con lector propio que comprueba los saldos línea a línea (D24). Hecho Bankinter; **Cajamar queda pendiente** (se hará cuando haya un extracto de ejemplo, sin bloquear las siguientes iteraciones).
- Reimportar un fichero repetido o que se solapa con otro no crea duplicados.
- Deshacer una importación completa.
- Reglas de categorización aplicadas al importar y al apuntar a mano. Al corregir una categoría, la app propone crear la regla.
- Edición masiva: recategorizar, etiquetar o borrar varios movimientos a la vez.

**Requisitos:** RF-IMP-01, RF-IMP-07 (Bankinter y Cajamar) · RF-MOV-07, RF-MOV-15 (edición masiva) · RNF-12.

**Cómo probarlo**
- *Automático:* ficheros reales anonimizados como casos de prueba (fichero → movimientos esperados); formatos españoles; reimportación sin duplicados; prioridad entre reglas que se contradicen.
- *Aceptación:*
  - [ ] Importar tus últimos 3 meses de Bankinter y de Cajamar.
  - [ ] El saldo resultante cuadra con el del banco.
  - [ ] Tras crear unas cuantas reglas, la mayoría de movimientos nuevos llegan categorizados.

**Necesito de ti:** un extracto de Bankinter y otro de Cajamar tal como los descarga la banca online (CSV o XLSX). Antes de guardarlos en el repositorio los anonimizamos: nombres, IBAN y conceptos personales.

---

### Iteración 4 · Captura con Apple Pay y conciliación (M)

**Objetivo:** que los pagos con el móvil aparezcan al momento y que nada se cuente dos veces.

**Entregables**
- Punto de entrada de captura con token personal y revocable, gestionable desde Ajustes.
- Plantilla del Atajo de iOS (automatización "Transacción") y guía paso a paso.
- **Motor de conciliación único**, que resuelve tres cosas:
  - Duplicados: el pago capturado se fusiona con el movimiento importado después (mismo importe, fecha cercana, comercio parecido). Los casos dudosos van a una bandeja de "posibles duplicados".
  - Parejas de transferencias entre cuentas propias en los movimientos importados.
  - Recurrentes: plantillas de nómina y recibos que generan una previsión de próximos cargos y se marcan como cumplidas cuando llega el movimiento real.
- Pagos denegados: la captura queda "pendiente" hasta que el extracto la confirma, o se descarta pasado un plazo.

**Requisitos:** RF-MOV-17 (punto de entrada y Atajo) · RF-MOV-09 · RF-MOV-04 (detección automática) · RF-MOV-06 (recurrentes manuales).

**Cómo probarlo**
- *Automático:* casos del motor (mismo importe en días distintos, dos cafés iguales el mismo día, devoluciones, pagos en divisa, pagos denegados); seguridad del punto de entrada (token inválido o revocado, límite de peticiones).
- *Aceptación:*
  - [ ] Pagar con Apple Pay en el iPhone y en el Watch, y ver el movimiento en segundos.
  - [ ] Importar después el extracto y comprobar que se fusiona sin duplicar.
  - [ ] Revocar el token y comprobar que el Atajo deja de poder enviar pagos.

> **Aplazado al despliegue (17/10/2026):** la captura está hecha y probada con tests, pero probarla con un pago real necesita la dirección definitiva (`miahorro.octogas.es`): con el túnel cambia en cada prueba. Pasa a la iteración 11 junto con el Atajo compartido.

---

### Iteración 5 · Objetivos de ahorro (M)

**Objetivo:** saber si vas en camino hacia tus metas.

**Entregables**
- Objetivos con nombre, importe, fecha, prioridad e imagen (un emoji; la foto propia llegará con los adjuntos, F2).
- Aportación mensual necesaria y fecha estimada con tu ritmo real.
- Financiación con cuentas completas o huchas virtuales; el saldo disponible de cada cuenta descuenta lo reservado.
- Tasa de ahorro objetivo con seguimiento por mes financiero.
- El modelo de "asignar dinero" se diseña aquí pensando ya en el presupuesto base cero de la iteración 6, para no rehacerlo.

**Requisitos:** RF-OBJ-01, 02, 03, 06.

**Cómo probarlo**
- *Automático:* cálculo de aportación y fecha; no se puede reservar más de lo que hay en la cuenta; la tasa de ahorro excluye transferencias.
- *Aceptación:*
  - [ ] Crear tu objetivo real (por ejemplo, la entrada del piso) y entender su progreso de un vistazo.

---

### Iteración 6 · Presupuestos (L)

**Objetivo:** controlar el gasto con el método que prefiera cada usuario.

**Entregables**
- Elegir el modo de presupuesto y poder cambiarlo.
- Modo límites: presupuesto por categoría con barra de progreso.
- Modo base cero: ingresos "por asignar", asignación a categorías y objetivos, y mover dinero entre categorías.
- Arrastre del sobrante o del exceso al mes siguiente.
- Todo respeta el día de inicio del mes financiero.

**Requisitos:** RF-PRS-01, 02, 03, 04.

**Cómo probarlo**
- *Automático:* en base cero, lo asignado más lo pendiente de asignar es igual a lo disponible; el arrastre conserva el dinero de un mes a otro; cambiar de modo no pierde datos; meses financieros que empiezan, por ejemplo, el día 25.
- *Aceptación:*
  - [ ] Usar durante un mes el modo que prefieras.
  - [ ] Probar el otro modo con datos de ejemplo.

---

### Iteración 7 · Préstamos (M)

**Objetivo:** tener tus deudas al día con un cuadro de amortización fiable.

**Entregables**
- Todos los tipos de préstamo, incluidos los préstamos entre particulares.
- Fijo, variable o mixto. El Euribor se introduce a mano en las tablas de referencia; la actualización automática es F2.
- Cuadro de amortización francés, lineal y con carencia, recalculado en cada revisión.
- Simulación y registro de amortizaciones anticipadas con la comisión de la Ley 5/2019.
- Deuda pendiente, intereses pagados y por pagar.
- El motor de amortización vive en el paquete `finance` y lo reutilizan las calculadoras.

**Requisitos:** RF-PRE-01, 02, 03, 05, 07, 09.

**Cómo probarlo**
- *Automático:*
  - Cuadros contrastados con casos verificados: simuladores de bancos, las funciones PAGO y PAGOINT de Excel y cuadros reales.
  - Propiedades: la suma de amortizaciones es igual al capital y el capital pendiente final es 0, también con tipo 0 %.
  - Redondeo al céntimo, con ajuste en la última cuota.
- *Aceptación:*
  - [ ] Dar de alta un préstamo real y comparar su cuadro con el del banco.

**Necesito de ti (opcional):** el cuadro de amortización de algún préstamo o hipoteca tuyo, como caso de prueba.

---

### Iteración 8 · Calculadoras (L)

**Objetivo:** simular decisiones grandes con cifras realistas para España.

**Entregables**
- Calculadoras de ahorro e interés compuesto, meta de ahorro, hipoteca, compra de vivienda, compra de coche, préstamo personal y fondo de emergencia.
- Escenarios guardables y comparables lado a lado.
- Precarga de tus datos reales: ingresos medios, ahorro mensual, liquidez y gastos esenciales.
- Tablas de referencia editables desde `/admin`, cada valor con fecha de vigencia y fuente: ITP y AJD por comunidad autónoma, IVA, impuesto de matriculación, límites de la Ley 5/2019, tramos de la base del ahorro y Euribor.
- Aviso de que los resultados son orientativos.

**Requisitos:** RF-CAL-01, 02, 03, 04, 07, 09, 10 · RF-PLT-02 (contenido de las tablas).

**Cómo probarlo**
- *Automático:* casos verificados por calculadora (compra de vivienda en varias comunidades contrastada con simuladores públicos, TAE con la fórmula oficial, coste total de un coche) y tests de que todas las tablas tienen fecha de vigencia.
- *Aceptación:*
  - [ ] Simular tu caso real de vivienda y de coche, y que las cifras te resulten razonables.
  - [ ] Revisar tú los valores de las tablas de tu comunidad autónoma.

---

### Iteración 9 · Inversiones (L)

**Objetivo:** llevar la cartera con el criterio fiscal correcto.

**Entregables**
- Fondos, ETF, acciones y planes de pensiones, identificados por ISIN o ticker.
- Operaciones: compra, venta, aportación periódica, dividendo, comisión, retención, *split* y traspaso entre fondos.
- Precio manual con fecha.
- FIFO con plusvalías realizadas y latentes.
- El valor de la cartera se suma al patrimonio.

**Requisitos:** RF-INV-01 (fondos, ETF, acciones, planes de pensiones), 02, 03 (manual), 05.

**Cómo probarlo**
- *Automático:* FIFO con casos difíciles (ventas parciales que cruzan varios lotes, traspasos que conservan fecha y coste, *splits*, comisiones dentro del coste).
- *Aceptación:*
  - [ ] Registrar tu cartera real.
  - [ ] Comparar las plusvalías con el informe fiscal de tu bróker, si lo tienes.

**Necesito de ti (opcional):** un informe fiscal o de operaciones de tu bróker como caso de prueba.

---

### Iteración 10 · Panel e informes (M)

**Objetivo:** ver de un vistazo cómo estás y cómo evolucionas.

**Entregables**
- Panel principal: patrimonio neto, liquidez, gasto del mes frente a presupuesto, objetivos, próximos cargos y vencimientos.
- Evolución del patrimonio neto (cuentas + inversiones − préstamos), con desglose.
- Ingresos frente a gastos y tasa de ahorro, por mes, por año o entre fechas a elegir.
- Gasto por categoría, comercio y etiqueta, comparado con el mes anterior y con el mismo mes del año anterior.
- Exportación de todos tus datos en CSV/JSON.

**Requisitos:** RF-INF-01, 02, 03, 04 · RF-PRE-09 (en el patrimonio) · RF-IMP-04.

**Cómo probarlo**
- *Automático:* el patrimonio en fechas pasadas cuadra con la suma de sus partes; la exportación contiene todos los datos y se puede volver a leer.
- *Aceptación:*
  - [ ] Revisar el panel con varias semanas de datos reales y que responda a tus preguntas habituales sin buscar.

---

### Iteración 11 · Cierre del MVP (M)

**Objetivo:** que puedas confiar en la plataforma para el día a día.

**Entregables**
- Rendimiento con 50.000 movimientos sintéticos.
- Modo sin conexión: consulta básica y cola de altas pendientes de enviar.
- Revisión de accesibilidad y del modo oscuro.
- Revisión de seguridad: dependencias, cabeceras y tests de autorización.
- Simulacro completo de recuperación en otra máquina.
- Documentación de uso y de operación.
- **Apple Pay en real** (aplazado desde la iteración 4), ya con la dirección definitiva:
  - Atajo compartido por enlace de iCloud, que al instalarlo solo pide el código de cada persona.
  - En Captura de pagos: botones «Instalar el Atajo» y «Copiar mi código», y los pasos de la automatización.
  - Aceptación: pagar con el iPhone y con el Watch, importar el extracto y que se una sin duplicar, y revocar el token.

**Requisitos:** RNF-02 (sin conexión), RNF-08, RNF-11, revisión de RNF-05 y RNF-07.

**Cómo probarlo**
- *Automático:* el panel carga en menos de 2 s con los datos sintéticos; Playwright en modo avión; auditoría automática de accesibilidad.
- *Aceptación:*
  - [ ] Apuntar un gasto sin conexión y que se sincronice al recuperarla.
  - [ ] Restaurar la copia de producción en local y que todo cuadre.
  - [ ] **Dos semanas de uso real sin incidencias graves → MVP terminado.**

---

## 6. Después del MVP: hito Familia

Fuera de este plan; se detallará al terminar el MVP. Incluirá:
- Recuperación de acceso por email, bienvenida, baja con borrado, texto de privacidad y panel de administración ampliado (RF-PLT-04 a 08).
- Plantillas de los bancos de tus familiares (RF-IMP-07).
- Receta de captura para Android, validada con un móvil real (RF-MOV-17).
- Las funcionalidades F2 que más hayas echado en falta usando el MVP.

---

## 7. Riesgos

| Riesgo | Cómo lo mitigamos |
|---|---|
| Romper octogas.es al desplegar | El despliegue es lo primero (iteración 0); contenedores aislados; copia de la configuración del proxy antes de tocarla, cambios revisados contigo y comprobación antes y después. |
| Fallos de seguridad en la autenticación propia | Librerías probadas, tests específicos, sin registro abierto y revisión en la iteración 11. |
| Errores en los cálculos financieros | Paquete aislado, `Decimal`, casos verificados y tests de propiedades. |
| El banco cambia el formato del extracto | Plantillas editables desde `/admin` y el asistente genérico como respaldo. |
| El Atajo de Apple Pay falla a veces | La importación del extracto confirma o completa lo que falte; bandeja de pendientes. |
| Complejidad del presupuesto base cero | Iteración propia, invariantes con tests y diseño conjunto con las huchas de la iteración 5. |
| Tablas de referencia desactualizadas | Cada valor con fecha de vigencia y fuente; revisión anual. |
| Pérdida de datos | Copias desde la iteración 0 y restauración probada en las iteraciones 0 y 11. |
| Recursos de la VPS | Límites por contenedor y medición del consumo en las iteraciones 0 y 11. |

---

## 8. Antes de empezar

**Tu equipo** ya tiene lo necesario: Git 2.52, Python 3.14, Node 22 y Docker 29 con Compose. Recomiendo instalar también `uv` para gestionar las dependencias de Python (opcional).

**Pendiente de decidir o aportar**

| # | Qué | Cuándo hace falta |
|---|---|---|
| A1 | Dónde vivirá el repositorio: GitHub privado con integración continua gratuita (GitHub Actions) o solo en local. | Al empezar la iteración 0 |
| A2 | Cómo desplegamos en la VPS: tú ejecutas los pasos con los scripts e instrucciones que yo preparo, o me das acceso SSH desde este equipo. Al haber producción, recomiendo que el primer despliegue lo hagas tú. | Final de la iteración 0 |
| A3 | Qué servidor web o proxy usa octogas.es y si corre en Docker. | Final de la iteración 0 |
| A4 | Almacenamiento externo gratuito para las copias, por ejemplo un Google Drive u OneDrive que ya tengas (se sube con rclone). | Final de la iteración 0 |
| A5 | Registro DNS de `miahorro.octogas.es` en DonDominio. | Final de la iteración 0 |
| A6 | Extractos de ejemplo de Bankinter (recibido) y Cajamar (pendiente). | Iteración 3 |
