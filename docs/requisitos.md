# MiAhorro: requisitos y funcionalidades

> **Estado:** v1.7 · 21/10/2026 · **Definición cerrada; en desarrollo** (ver [plan-mvp.md](plan-mvp.md)).
>
> Este documento es la referencia del proyecto y se irá actualizando. Cada requisito tiene un ID para poder comentarlo con precisión (por ejemplo, "quita RF-CTA-11" o "sube RF-PRE-06 al MVP").

**Prioridades**

| Código | Significado |
|---|---|
| **MVP** | Imprescindible para la primera versión usable |
| **F2** | Segunda fase: automatización y análisis |
| **F3** | Tercera fase: mejoras y asistente |
| **Idea** | Por validar; puede descartarse |
| **Familia** | Necesario para abrir la plataforma a tus 2–3 familiares (ver §7) |
| **Futuro** | Solo si algún día se abre al público; queda documentado pero no está previsto |
| **Aplazado** | Fuera del plan actual por una decisión tomada (p. ej. sin IA); se reevaluará |
| **Descartado** | No se hará |

---

## 1. Visión

Una plataforma gratuita de finanzas personales para España (web + iPhone) que reúna en un único sitio el patrimonio y el flujo de dinero: cuentas, inversiones, préstamos, ingresos y gastos. Debe pedir la mínima entrada manual posible y ayudar a tomar decisiones: ahorrar para un objetivo, comprar vivienda o coche, amortizar o invertir.

Empieza como herramienta de uso propio y después se abre a 2–3 familiares cercanos (ver §7). Se diseña multiusuario desde el primer día, de modo que abrirla a más gente en el futuro no obligue a rehacerla.

### Objetivos

| ID | Objetivo |
|---|---|
| O1 | Saber en todo momento cuánto tengo (patrimonio neto) y cómo evoluciona. |
| O2 | Saber en qué se va el dinero sin tener que apuntarlo todo a mano. |
| O3 | Controlar lo que generan las cuentas e inversiones y lo que cuestan los préstamos. |
| O4 | Fijar objetivos de ahorro y saber si voy en camino de cumplirlos. |
| O5 | Simular decisiones grandes antes de tomarlas. |
| O6 | Facilitar la declaración de la renta con un resumen fiscal orientativo. |

### Principios

- **Automatizar primero.** La entrada manual es el último recurso y, cuando haga falta, debe ser rápida.
- **Pensada para España.** Euro, formatos es-ES, productos y fiscalidad españoles (Euribor, ITP, retención del 19 %, Norma 43…).
- **Solo lectura.** La plataforma nunca mueve dinero ni inicia pagos.
- **Privacidad.** Datos financieros cifrados y el menor número posible de terceros.
- **Multiusuario desde el diseño.** Los datos de cada usuario están aislados, aunque al principio solo haya uno.
- **Sin actividades reguladas.** Nada que exija ser entidad autorizada: ni agregación bancaria PSD2 propia ni asesoramiento de inversión.
- **Coste cero.** Todo funciona en la VPS que ya tienes; no se contrata ningún servicio de pago.
- **Precisión.** Importes en decimal exacto, nunca en coma flotante; todos los cálculos con tests.

---

## 2. Conceptos clave

| Concepto | Descripción |
|---|---|
| Entidad | Banco, bróker, exchange… Agrupa cuentas (útil, por ejemplo, para el límite del Fondo de Garantía de Depósitos). |
| Cuenta | Contenedor de saldo: corriente, ahorro, depósito, tarjeta, efectivo, bróker, wallet cripto… |
| Movimiento | Entrada o salida de dinero en una cuenta: ingreso, gasto o transferencia interna. |
| Categoría | Clasificación jerárquica de movimientos (Vivienda › Alquiler). |
| Regla | Condición → acción automática (si el concepto contiene "MERCADONA" → categoría Supermercado). |
| Activo | Posición de inversión o bien con valor (fondo, ETF, acción, cripto, vivienda, coche). |
| Pasivo | Deuda: hipoteca, préstamo, tarjeta aplazada. |
| Objetivo | Meta de ahorro con importe y fecha. |
| Presupuesto | Límite de gasto por categoría y periodo. |
| Recurrente | Movimiento que se repite: nómina, alquiler, recibos, suscripciones. |
| Fuente | Origen de los datos: manual, importación de extractos, Apple Pay, bróker… |

---

## 3. Módulos funcionales

### 3.1 Cuentas (CTA)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-CTA-01 | Alta, edición y archivado de cuentas: corriente, ahorro remunerada, depósito a plazo, tarjeta de crédito, efectivo, monedero (Revolut, PayPal…), cuenta de valores/bróker, wallet cripto. | MVP |
| RF-CTA-02 | Datos por cuenta: entidad, alias, IBAN (enmascarado), divisa, titularidad (individual/compartida), saldo inicial y fecha. | MVP |
| RF-CTA-03 | Remuneración configurable: TIN/TAE, **por tramos** (p. ej. 2 % hasta 10.000 € y 0 % el resto), periodicidad de liquidación (diaria, mensual, trimestral, al vencimiento) y retención (19 % por defecto). | MVP |
| RF-CTA-04 | Histórico de cambios de tipo de interés con fecha de vigencia (los bancos cambian las condiciones). | MVP |
| RF-CTA-05 | Cálculo de intereses devengados y previstos (bruto y neto) y comparación con lo realmente abonado. | F2 |
| RF-CTA-06 | Promociones con fecha de fin (p. ej. "4 % durante 6 meses") y aviso antes de que caduquen. | F2 |
| RF-CTA-07 | Depósitos a plazo: importe, plazo, vencimiento, renovación automática y penalización por cancelación anticipada; aviso de vencimiento. | MVP |
| RF-CTA-08 | Conciliación de saldo: si el saldo real difiere del calculado, generar un movimiento de ajuste. | MVP |
| RF-CTA-09 | Aviso de concentración si en una entidad se superan los 100.000 € cubiertos por el Fondo de Garantía de Depósitos. | F2 |
| RF-CTA-10 | Tarjetas de crédito: límite, día de corte y de cargo, modalidad (fin de mes o aplazado con interés). La deuda pendiente cuenta como pasivo. | F2 |
| RF-CTA-11 | "¿Dónde tengo mejor el dinero?": rentabilidad neta anual de cada cuenta frente a alternativas que introduzca. | F3 |

### 3.2 Inversiones (INV)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-INV-01 | Tipos de activo: fondos de inversión, ETF, acciones, planes de pensiones/EPSV, letras del Tesoro y bonos, cripto, roboadvisor (como cartera), crowdlending y otros (oro, inmuebles). | MVP: fondos, ETF, acciones, planes de pensiones · F2: resto |
| RF-INV-02 | Operaciones: compra, venta, aportación periódica, dividendo/cupón, comisión, retención, *split* y **traspaso entre fondos** (sin tributación, conservando fecha y coste de adquisición). | MVP |
| RF-INV-03 | Identificación por ISIN/ticker. El precio o valor liquidativo manual siempre está disponible; la actualización automática diaria usa solo fuentes gratuitas, y si un activo no está cubierto se queda en manual. | MVP: manual · F2: automático |
| RF-INV-04 | Rentabilidad: plusvalía latente, rentabilidad simple, TIR/XIRR (ponderada por dinero) y TWR (ponderada por tiempo), por activo, cartera y total. | F2 |
| RF-INV-05 | Ganancias y pérdidas realizadas por método **FIFO** (el que exige Hacienda para valores homogéneos). | MVP |
| RF-INV-06 | Distribución de la cartera por tipo de activo, región, divisa y entidad; cartera objetivo y desviación para rebalancear. | F2 |
| RF-INV-07 | Aportaciones periódicas programadas que se generan solas o se concilian con el cargo del banco. | F2 |
| RF-INV-08 | Calendario e histórico de dividendos y cupones. | F3 |
| RF-INV-09 | Bienes (vivienda, coche) con valor estimado actualizable a mano para el patrimonio neto; depreciación automática configurable para vehículos. | F2 |
| RF-INV-10 | Renta fija y ahorro garantizado: letras del Tesoro (compra al descuento, vencimiento), bonos, fondos monetarios. | F2 |

### 3.3 Ingresos y gastos (MOV)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-MOV-01 | Alta manual rápida desde el móvil (≤ 3 toques): importe, cuenta, categoría, fecha (hoy por defecto) y concepto. | MVP |
| RF-MOV-02 | Categorías y subcategorías personalizables con icono y color; conjunto inicial adaptado a España. | MVP |
| RF-MOV-03 | Etiquetas libres (p. ej. `#viaje-japon-2027`) y notas. | MVP |
| RF-MOV-04 | Transferencias entre cuentas propias: no cuentan como ingreso ni gasto; detección automática de la pareja salida/entrada. | MVP |
| RF-MOV-05 | Dividir un movimiento en varias categorías (ticket del súper con productos de droguería). | F2 |
| RF-MOV-06 | Movimientos recurrentes (nómina, alquiler, recibos) con previsión. Detección automática de suscripciones y recibos, y aviso de subidas de precio. | MVP: manual · F2: detección |
| RF-MOV-07 | Reglas de categorización automática (por concepto, comercio, importe, cuenta). Una regla también puede decir que el movimiento es una transferencia con otra cuenta propia (p. ej. el cargo mensual de la tarjeta de crédito). Si corrijo una categoría, la app ofrece crear la regla. | MVP |
| RF-MOV-08 | Normalización de comercios ("COMPRA TARJ. 1234 MERCADONA S.A. VALENCIA" → "Mercadona"). | F2 |
| RF-MOV-09 | Detección y fusión de duplicados (p. ej. un pago capturado por Apple Pay y luego recibido del banco). | MVP |
| RF-MOV-10 | Adjuntos: foto del ticket o factura (imagen/PDF). | F2 |
| RF-MOV-11 | Lectura automática de tickets: importe, fecha y comercio. | Aplazado (sin IA) |
| RF-MOV-12 | Multi-divisa: importe original y equivalente en euros al tipo del día (BCE). | F2 |
| RF-MOV-13 | Estado pendiente/confirmado y marca de "reembolsable" (gastos que me tienen que devolver la empresa o un amigo). | F2 |
| RF-MOV-14 | Gastos compartidos (pareja, amigos): reparto y saldo de quién debe a quién, al estilo Splitwise. | Idea |
| RF-MOV-15 | Búsqueda, filtros avanzados y edición masiva. Al ver una cuenta, cada movimiento muestra el saldo que quedó tras él. | MVP |
| RF-MOV-16 | Garantías: guardar la factura de compras importantes y avisar antes de que termine la garantía. | Idea |
| RF-MOV-17 | Captura automática de pagos desde el móvil mediante un punto de entrada de la API con token personal y revocable. En iPhone lo usa el Atajo de Apple Pay, con plantilla y guía. En Android puede usarlo una app de automatización gratuita (p. ej. MacroDroid) que lea la notificación de pago y la envíe al mismo punto de entrada. | MVP: punto de entrada y Atajo · Familia: receta Android, a validar con un móvil real |

### 3.4 Préstamos y deudas (PRE)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-PRE-01 | Tipos: hipoteca, préstamo personal, préstamo de coche, financiación al consumo, línea de crédito y préstamos entre particulares (debo / me deben). | MVP |
| RF-PRE-02 | Datos: capital, fecha de firma, plazo, TIN, TAE, sistema de amortización (francés por defecto; también lineal y con carencia), día de cargo, cuenta de cargo y comisiones. | MVP |
| RF-PRE-03 | Tipo fijo, variable o mixto: índice (Euribor 12 meses) + diferencial, periodicidad de revisión (anual/semestral) y periodo fijo inicial. | MVP |
| RF-PRE-04 | Bonificaciones del diferencial (nómina, seguros, tarjeta…) con su coste anual, para calcular el coste real del préstamo. | F2 |
| RF-PRE-05 | Cuadro de amortización completo (cuota, intereses, capital, capital pendiente), recalculado en cada revisión. | MVP |
| RF-PRE-06 | Euribor actualizado automáticamente y aviso de la próxima revisión con la cuota estimada. | F2 |
| RF-PRE-07 | Amortizaciones anticipadas: registro y simulación (reducir cuota o reducir plazo) con el ahorro de intereses y la comisión aplicable según los límites de la Ley 5/2019. | MVP |
| RF-PRE-08 | Conciliación: reconocer el cargo mensual del banco y separarlo en intereses (gasto) y capital (reduce la deuda). | F2 |
| RF-PRE-09 | Deuda pendiente, intereses pagados y por pagar y fecha de fin, integrados en el patrimonio neto. | MVP |
| RF-PRE-10 | Estrategias para liquidar varias deudas: bola de nieve frente a avalancha. | F3 |

### 3.5 Objetivos de ahorro (OBJ)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-OBJ-01 | Crear objetivos con nombre, importe, fecha, prioridad e imagen (p. ej. "Entrada del piso: 60.000 € para 2029"). | MVP |
| RF-OBJ-02 | Aportación mensual necesaria y fecha estimada de consecución con el ritmo actual. | MVP |
| RF-OBJ-03 | Financiar objetivos asignando cuentas completas o "huchas virtuales" (una parte del saldo de una cuenta). | MVP |
| RF-OBJ-04 | Proyección con la rentabilidad esperada del dinero asignado y con inflación. | F2 |
| RF-OBJ-05 | Fondo de emergencia: objetivo calculado automáticamente como N meses de gastos esenciales reales. | F2 |
| RF-OBJ-06 | Objetivo global de tasa de ahorro (p. ej. ahorrar el 25 % de los ingresos) con seguimiento mensual. | MVP |
| RF-OBJ-07 | Reglas de aportación: % de cada nómina, redondeo de gastos o sobrante de fin de mes (como recordatorio, sin mover dinero). | F3 |
| RF-OBJ-08 | Avisos de progreso: "vas 300 € por detrás" o "a este ritmo lo consigues en marzo". | F2 |
| RF-OBJ-09 | Crear un objetivo directamente desde el resultado de una calculadora. | F2 |

### 3.6 Presupuestos (PRS)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-PRS-01 | Cada usuario elige su modo de presupuesto y puede cambiarlo: **límites por categoría** o **base cero**. | MVP |
| RF-PRS-02 | Modo límites: presupuesto mensual en las categorías que elija, con barra de progreso. | MVP |
| RF-PRS-03 | Modo base cero (al estilo YNAB): cada euro que entra se asigna a una categoría u objetivo, con el saldo "por asignar" siempre visible y la posibilidad de mover dinero entre categorías. | MVP |
| RF-PRS-04 | Arrastre del sobrante o exceso al mes siguiente (imprescindible en base cero, opcional en límites). | MVP |
| RF-PRS-05 | Plantillas para empezar rápido: 50/30/20 o reparto a partir del gasto real de los últimos meses. | F2 |
| RF-PRS-06 | Gastos anuales o irregulares (seguro del coche, IBI, regalos de Navidad) prorrateados por meses. | F2 |
| RF-PRS-07 | Alertas al alcanzar el 80 % y el 100 %. | F2 |

### 3.7 Calculadoras y simuladores (CAL)

Todas las calculadoras comparten estas capacidades: guardar parámetros como "escenario", comparar escenarios lado a lado, precargar mis datos reales (ingresos, ahorro mensual, patrimonio) y crear un objetivo a partir del resultado.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-CAL-01 | **Ahorro e interés compuesto**: capital inicial, aportación periódica, rentabilidad, años, inflación e impuestos → valor final nominal y real, con gráfico. | MVP |
| RF-CAL-02 | **Meta de ahorro**: cuánto debo ahorrar al mes para tener X en N años, o cuándo llegaré a X con mi ahorro actual. | MVP |
| RF-CAL-03 | **Hipoteca**: cuota, intereses totales y cuadro; fija frente a variable frente a mixta con escenarios de Euribor; efecto de las bonificaciones. | MVP |
| RF-CAL-04 | **Compra de vivienda**: precio y comunidad autónoma; obra nueva (IVA 10 % + AJD) o segunda mano (ITP según comunidad); notaría, registro, gestoría y tasación; % financiado (80 % habitual) → ahorro total necesario. También ratio de endeudamiento (30–35 % de los ingresos netos), precio máximo asumible con mis ingresos y fecha en la que podría comprar con mi ritmo de ahorro. | MVP |
| RF-CAL-05 | **Alquilar o comprar**: coste total a N años con coste de oportunidad, revalorización, IBI, comunidad, seguro y mantenimiento. | F2 |
| RF-CAL-06 | **Amortizar hipoteca o invertir**: ahorro de intereses frente a rentabilidad esperada neta de impuestos. | F2 |
| RF-CAL-07 | **Compra de coche**: contado, préstamo, financiación del concesionario con cuota final (multiopción/PCP), renting o leasing. Coste total de propiedad por año y por km: impuesto de matriculación, seguro, IVTM, ITV, combustible o electricidad, mantenimiento y depreciación. | MVP |
| RF-CAL-08 | **Compra de otros objetos**: pagar al contado, financiar o ahorrar N meses; desenmascarar el "0 % TIN" calculando la TAE real con comisiones; coste expresado en horas de trabajo. | F2 |
| RF-CAL-09 | **Préstamo personal**: cuota, TAE real y coste total; comparación de ofertas. | MVP |
| RF-CAL-10 | **Fondo de emergencia**: cuántos meses tengo cubiertos y cuánto me falta. | MVP |
| RF-CAL-11 | **Independencia financiera (FIRE) y jubilación**: patrimonio necesario (regla del 4 %, configurable), años hasta alcanzarlo y pensión pública estimada introducida a mano. | F2 |
| RF-CAL-12 | **Comparador de cuentas remuneradas y depósitos**: rentabilidad neta tras retención y tramos. | F2 |
| RF-CAL-13 | **Inflación**: poder adquisitivo de una cantidad a lo largo del tiempo con el IPC del INE. | F3 |
| RF-CAL-14 | **Plan de pensiones**: ahorro fiscal de la aportación (límite individual 1.500 €/año) frente a un fondo indexado. | F3 |
| RF-CAL-15 | **Nómina neta**: bruto anual → neto mensual (IRPF + Seguridad Social, 12 o 14 pagas). | Idea |

### 3.8 Panel e informes (INF)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-INF-01 | Panel principal: patrimonio neto, liquidez, gasto del mes frente a presupuesto, progreso de objetivos y próximos cargos. | MVP |
| RF-INF-02 | Evolución del patrimonio neto (activos − pasivos) con desglose. | MVP |
| RF-INF-03 | Ingresos frente a gastos por mes y tasa de ahorro. Los informes se pueden ver por mes, por año o entre fechas a elegir. | MVP |
| RF-INF-04 | Gasto por categoría, comercio y etiqueta, comparado con el mes anterior y con el mismo mes del año anterior. | MVP |
| RF-INF-05 | Previsión de saldo a 30/90 días con recurrentes y préstamos: "¿llego a fin de mes?". | F2 |
| RF-INF-06 | Diagrama de flujo (Sankey): ingresos → categorías de gasto → ahorro. | F2 |
| RF-INF-07 | Calendario de pagos e ingresos previstos, suscribible como iCal desde el calendario del iPhone. | F2 |
| RF-INF-08 | Resumen anual ("tu año en cifras"). | F3 |
| RF-INF-09 | Informes exportables a PDF/Excel. | F3 |

### 3.9 Alertas y notificaciones (ALR)

Canales: notificación push (PWA en iOS), email y, opcionalmente, Telegram.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-ALR-01 | Saldo bajo o riesgo de descubierto previsto en una cuenta. | F2 |
| RF-ALR-02 | Presupuesto al 80 % y al 100 %. | F2 |
| RF-ALR-03 | Gasto inusual (muy por encima de lo habitual en ese comercio o categoría) o cargo duplicado. | F2 |
| RF-ALR-04 | Vencimientos: depósito, promoción de cuenta, revisión de hipoteca, fin de garantía, renovación de seguro. | F2 |
| RF-ALR-05 | Recordatorio de importar extractos cuando una cuenta lleva varios días sin datos nuevos. | F2 |
| RF-ALR-06 | Fallo de sincronización de una fuente. | F2 |
| RF-ALR-07 | Resumen semanal o mensual. | F3 |

### 3.10 Fiscalidad española (FIS)

Orientativo: no sustituye a un asesor fiscal.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-FIS-01 | Resumen anual para la renta: intereses (rendimientos del capital mobiliario), dividendos y retenciones soportadas. | F2 |
| RF-FIS-02 | Ganancias y pérdidas patrimoniales realizadas (FIFO), con aviso de la regla de los dos meses (recompra de valores homogéneos). | F2 |
| RF-FIS-03 | Aportaciones a planes de pensiones del año y margen restante hasta el límite. | F2 |
| RF-FIS-04 | Pérdidas pendientes de compensar en los cuatro años siguientes. | F3 |
| RF-FIS-05 | Simulación del impuesto de la base del ahorro (tramos configurables) antes de vender. | F3 |
| RF-FIS-06 | Aviso de posible obligación de Modelo 720/721 (bienes o cripto en el extranjero por encima de 50.000 €). | F3 |

### 3.11 Importación, exportación y copias (IMP)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-IMP-01 | Importador genérico de CSV/XLSX con asistente de mapeo de columnas, capaz de leer el extracto de cualquier banco. La configuración se guarda como plantilla reutilizable y compartida entre todos los usuarios. | MVP |
| RF-IMP-02 | Importar **Norma 43** (formato estándar de extractos de la banca española; un único lector sirve para todos los bancos que lo ofrecen) y OFX/QIF. | F2 |
| RF-IMP-03 | Importar extractos PDF de bancos o brókers que no exportan en otro formato. | MVP: extractos PDF de Bankinter (hecho) y Cajamar (pendiente de un extracto de ejemplo), con lector propio de cada banco que comprueba los saldos (D24) · resto aplazado (sin IA) |
| RF-IMP-04 | Exportar todos los datos (CSV/JSON). | MVP |
| RF-IMP-05 | Copias de seguridad automáticas cifradas y restauración probada. | MVP |
| RF-IMP-06 | Migrar histórico desde otras herramientas (Excel propio, Fintonic…). | Descartado (D14) |
| RF-IMP-07 | Plantillas predefinidas por banco, creadas a partir de ficheros de ejemplo reales: **Bankinter y Cajamar** primero; después los bancos de tus familiares y el resto de los principales (Santander, BBVA, CaixaBank, Sabadell, Unicaja, Kutxabank, Abanca, Ibercaja, ING, Openbank, Revolut, N26, Trade Republic, MyInvestor…). | MVP: Bankinter y Cajamar · Familia: bancos de tus familiares · F2: resto |
| RF-IMP-08 | Detección automática del banco y de la plantilla a partir del fichero subido. | F2 |

### 3.12 Asistente con IA (IA), aplazado

**Decisión D12: sin IA de momento.** El módulo queda documentado por si se retoma. Supondría enviar datos (que pueden anonimizarse) a un proveedor externo y un coste por uso.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-IA-01 | Categorizar los movimientos que no encajan con ninguna regla. | Aplazado |
| RF-IA-02 | Preguntas en lenguaje natural: "¿cuánto gasté en restaurantes este verano?". | Aplazado |
| RF-IA-03 | Análisis mensual: suscripciones olvidadas, subidas de recibos, oportunidades de ahorro. | Aplazado |
| RF-IA-04 | Lectura de tickets y extractos PDF (base de RF-MOV-11 y RF-IMP-03). | Aplazado |

### 3.13 Usuarios, seguridad y ajustes (USR)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-USR-01 | Inicio de sesión con passkey (Face ID) y/o contraseña con segundo factor. La passkey es el método principal: sirve sola y también como segundo factor tras la contraseña. La app de códigos (TOTP) es la alternativa para dispositivos sin passkeys. Los códigos de recuperación son obligatorios con TOTP y opcionales con passkey. | MVP |
| RF-USR-02 | Bloqueo por inactividad y modo "ocultar importes" para usar la app en público. | F2 |
| RF-USR-03 | Hogares compartidos: invitar a otra persona (pareja, familia) a un espacio común con permisos por cuenta. | F2 |
| RF-USR-04 | Preferencias: divisa principal, día de inicio del mes financiero (p. ej. el día que cobro la nómina), idioma y tema claro/oscuro. | MVP |
| RF-USR-05 | Registro de actividad de cambios y de integraciones. | F2 |

### 3.14 Plataforma multiusuario (PLT)

Requisitos para que varias personas usen la plataforma. Con 2–3 familiares basta con una versión sencilla; lo marcado como "Futuro" solo haría falta si se abriera al público.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-PLT-01 | Aislamiento total de los datos entre usuarios, con tests que lo verifiquen. | MVP |
| RF-PLT-02 | Tablas de referencia comunes, mantenidas desde administración: ITP por comunidad autónoma, tramos fiscales, Euribor, límites legales, plantillas de importación por banco y categorías por defecto. | MVP |
| RF-PLT-03 | Registro abierto desde la app (nombre, email y contraseña), seguido de la configuración obligatoria del segundo factor. El primer usuario registrado es el administrador. Salvaguardas: tope de usuarios (20 por defecto) e interruptor para cerrar el registro. La recuperación de acceso por email queda para el hito Familia. | MVP |
| RF-PLT-04 | Bienvenida sencilla: crear cuentas, elegir modo de presupuesto, instalar la PWA y configurar el Atajo de Apple Pay con una guía paso a paso. Opción de explorar con datos de ejemplo. | Familia |
| RF-PLT-05 | Darse de baja con borrado definitivo de todos los datos, con descarga previa. | Familia |
| RF-PLT-06 | Texto breve de privacidad (qué se guarda, dónde y quién tiene acceso) y aviso de que las calculadoras son orientativas. | Familia |
| RF-PLT-07 | Emails de invitación y recuperación con un servicio gratuito (SMTP de una cuenta propia o plan gratuito de un proveedor de la UE). Las alertas van preferentemente por notificación push. | Familia |
| RF-PLT-08 | Panel de administración: usuarios, invitaciones, tablas de referencia, estado del sistema y errores de importación, sin mostrar los datos financieros de cada usuario. | Familia |
| RF-PLT-09 | Textos legales completos (aviso legal, términos de uso, política de privacidad formal). | Futuro |
| RF-PLT-10 | Protección adicional frente a abuso del registro abierto: límites de peticiones por IP y verificación anti-bots. El bloqueo tras intentos fallidos, el tope de usuarios y el interruptor del registro ya están incluidos (RNF-05, RF-PLT-03). | Futuro |
| RF-PLT-11 | Soporte (formulario y preguntas frecuentes) y página pública de presentación. | Futuro |

---

## 4. Integraciones y automatización

Decisión D2: los movimientos entran por **alta manual, Atajo de Apple Pay e importación de extractos**. El open banking queda fuera por ahora (ver 4.2). El motor de duplicados (RF-MOV-09) reconcilia las fuentes para que nada se cuente dos veces.

### 4.1 Mapa de fuentes

| Fuente | Cómo | Automatización | Coste | Notas |
|---|---|---|---|---|
| Bancos (cuentas y tarjetas) | Exportar CSV/XLSX (MVP) o Norma 43 (F2) desde la banca online e importarlo | Media: manual cada pocas semanas | Gratis | Fuente principal de movimientos bancarios. Importador genérico válido para cualquier banco y plantillas predefinidas, empezando por Bankinter y Cajamar (RF-IMP-07). |
| Pagos con Apple Pay (iPhone/Watch) | Automatización "Transacción" de la app Atajos (iOS 17+) que llama a la API de la plataforma | Alta e instantánea | Gratis | Envía importe, comercio y tarjeta en el momento del pago, sin app nativa. Cada usuario genera un token personal revocable e instala una plantilla de atajo compartida, con guía paso a paso. Fallos conocidos: a veces no se dispara o se dispara con pagos denegados; el extracto importado lo confirma después. |
| Pagos con el móvil en Android | App de automatización gratuita (p. ej. MacroDroid) que lee la notificación de pago (Google Wallet o la app del banco) y llama a la misma API que el Atajo | Alta, por validar | Gratis | No hay un disparador oficial como en iPhone: depende del texto de la notificación, que varía según el banco. Si no funciona bien, en Android quedan el alta manual y la importación (RF-MOV-17). |
| Bizum | Sin API pública para particulares | A través de los extractos importados | — | Se categoriza con reglas ("BIZUM DE…"). |
| ~~Open banking (PSD2)~~ | Agregador bancario | — | — | **Descartado por ahora** (ver 4.2). |
| Emails (avisos del banco, facturas, Amazon…) | Reenvío a una dirección de la plataforma y extracción de datos | Media | Bajo | Opcional; útil para adjuntar facturas automáticamente. |
| Interactive Brokers | Flex Query (informes por API oficial) | Alta | Gratis | |
| Indexa Capital | API propia | Alta | Gratis | Pendiente de confirmar documentación y alcance. |
| Trade Republic, MyInvestor, DEGIRO, etc. | Sin API oficial: importar CSV/PDF de operaciones | Media | Gratis | Las APIs no oficiales son frágiles y pueden incumplir las condiciones de uso; se descartan. |
| Exchanges cripto (Binance, Kraken, Coinbase…) | API con clave de solo lectura | Alta | Gratis | |
| Wallets cripto propias | Dirección pública consultada en un explorador de bloques | Alta | Gratis | |
| Precios de ETF y acciones | Plan gratuito de un proveedor de datos de mercado (Twelve Data, Alpha Vantage…) | Alta: diaria | Gratis | Los límites diarios de los planes gratuitos bastan para la cartera de 2–3 personas. Si un valor no está cubierto, precio manual. |
| Valor liquidativo de fondos | Fuente gratuita cuando exista para el ISIN; si no, entrada manual | Media | Gratis | Punto débil: no hay una fuente oficial gratuita. Validar con los fondos concretos que tengáis. |
| Precios de cripto | API gratuita de CoinGecko | Alta: diaria | Gratis | |
| Euribor | Banco de España / API de datos del BCE | Alta: mensual | Gratis | Para revisar hipotecas se usa el Euribor a un año que publica mensualmente el Banco de España. |
| Tipos de cambio | API del BCE | Alta: diaria | Gratis | |
| IPC | API del INE | Alta: mensual | Gratis | Para las calculadoras de inflación. |
| Apple FinanceKit (datos de Wallet) | — | — | — | Solo disponible en EE. UU. y Reino Unido; descartado mientras no llegue a España. |

### 4.2 Por qué no open banking (por ahora)

- **Para un producto abierto a terceros**, la agregación bancaria exige un contrato comercial con un agregador (Enable Banking, Tink, TrueLayer, Salt Edge…) o una licencia propia de proveedor de información sobre cuentas (AISP). En un producto gratuito, ese coste y esas obligaciones no compensan al principio.
- **Las opciones gratuitas no sirven para terceros:** el modo restringido de Enable Banking solo funciona con las cuentas del propio titular, y GoCardless Bank Account Data (antes Nordigen) habría cerrado las altas nuevas.
- **Cobertura limitada:** aun con open banking, PSD2 normalmente da solo saldos y movimientos de cuentas y tarjetas; no depósitos, fondos, planes de pensiones ni préstamos.
- **Se puede reevaluar:** con la arquitectura de conectores independientes (RNF-12) se añadiría sin rehacer nada. Ahora que los usuarios son solo tú y tu familia, el modo gratuito de Enable Banking podría automatizar **tus** cuentas de Bankinter y Cajamar. Sus términos lo limitan a las cuentas del propio titular, así que no cubriría las de tus familiares. Descartado de momento (D20), para que uses la plataforma igual que ellos.

---

## 5. Requisitos no funcionales (RNF)

| ID | Requisito |
|---|---|
| RNF-01 | Web responsive y *mobile-first*: el uso diario será desde el iPhone. |
| RNF-02 | PWA instalable en iOS: icono en la pantalla de inicio, pantalla completa, notificaciones push (iOS 16.4+), consulta básica sin conexión y cola de altas offline. |
| RNF-03 | Español (es-ES), euro y formatos españoles de fecha y número. Textos preparados para traducción aunque solo se publique en español. Soporte multi-divisa. |
| RNF-04 | Aritmética decimal exacta en todos los importes; política de redondeo al céntimo documentada. |
| RNF-05 | Seguridad: HTTPS, cifrado en reposo de credenciales y tokens de integraciones, mínimo privilegio (solo lectura), protección frente a fuerza bruta. |
| RNF-06 | Privacidad: datos alojados en la UE; sin analítica de terceros ni cookies de seguimiento. Si se mide el uso, con una herramienta propia y sin cookies, lo que evita el banner de consentimiento. |
| RNF-07 | Disponibilidad de uso personal: se toleran caídas breves, pero nunca pérdida de datos. Copia diaria cifrada con 30 días de retención, guardada **fuera** de la VPS en un almacenamiento gratuito, además de los snapshots de netcup. |
| RNF-08 | Rendimiento: el panel carga en menos de 2 s con 10 años de movimientos (unos 50.000). |
| RNF-09 | Coste adicional cero: todo funciona en la VPS de netcup existente (VPS Lite 1 G12s: 2 vCores, 4 GB de RAM, 80 GB de SSD) y solo se usan planes gratuitos de servicios externos. |
| RNF-10 | Tests automáticos de todos los cálculos financieros (amortización, intereses, FIFO, calculadoras) contra casos verificados. |
| RNF-11 | Accesibilidad básica: contraste, tamaños de toque y modo oscuro. |
| RNF-12 | Cada integración es un conector independiente: si una falla, el resto sigue funcionando. |
| RNF-13 | Protección de datos: con 2–3 familiares y sin fines comerciales, el uso puede encajar en la exención de actividades personales o domésticas del RGPD. Aun así: consentimiento informado de cada familiar (RF-PLT-06), datos solo en la UE y borrado a petición (RF-PLT-05). Si algún día se abre al público, habrá que cumplir el RGPD completo y revisarlo con un profesional. |
| RNF-14 | Dimensionado para unos pocos usuarios en una VPS de 4 GB de RAM, con un modelo de datos multiusuario que permita crecer sin rehacerlo. |
| RNF-15 | Observabilidad: registro de errores y monitorización, sin datos financieros en los logs. |
| RNF-16 | Despliegue reproducible en la VPS, HTTPS automático y actualizaciones de seguridad del sistema operativo automáticas. |
| RNF-17 | Servida en `https://miahorro.octogas.es`. El HTTPS es imprescindible para instalar la PWA, recibir notificaciones push y que el Atajo de Apple Pay envíe datos de forma segura. Requiere un registro DNS en DonDominio que apunte a la VPS. |
| RNF-18 | Convivencia con octogas.es (en producción en la misma VPS): contenedores propios con límites de memoria y CPU; base de datos y usuario de base de datos propios; red Docker propia. Cookies de sesión solo para el subdominio (sin atributo `Domain`, prefijo `__Host-`) para no mezclarse con las de octogas.es. Copias independientes. Desplegar MiAhorro nunca reinicia ni modifica servicios de octogas.es, salvo añadir el host virtual del subdominio en el proxy. |

---

## 6. Plataforma y opciones para iPhone (sin Mac)

| Opción | Instalación | Coste | A favor | En contra |
|---|---|---|---|---|
| **A. PWA** (web instalable) | Safari → Compartir → Añadir a pantalla de inicio | 0 € | Un único código; sin App Store; notificaciones push; actualizaciones inmediatas | Sin widgets ni acceso a datos nativos; segundo plano limitado |
| **B. App nativa con React Native + Expo**, compilada en la nube (EAS Build) | TestFlight / App Store | 99 $/año (Apple Developer Program) + plan de EAS | Widgets, Face ID nativo, mejor experiencia; se compila y publica desde Windows | Un segundo cliente que mantener; revisión de Apple |
| **C. Web envuelta con Capacitor** + compilación en CI con macOS (GitHub Actions, Codemagic) | TestFlight / App Store | 99 $/año + minutos de CI | Reutiliza la web | Apple puede rechazar apps que son solo una web; depuración más incómoda |

**Decisión D3:** empezar con **A**. Cubre casi todo el uso diario, y la captura de Apple Pay se resuelve con Atajos, que no necesita app nativa. La API irá separada del frontend para poder hacer **B** más adelante si se echan en falta widgets, presencia en la App Store u otras capacidades nativas.

---

## 7. Lanzamiento y fases

**Decisiones D5 y D8:** primero la usas tú y después la abres a 2–3 familiares cercanos. La apertura al público no está prevista.

El orden de desarrollo del MVP, con entregables y pruebas, está en [plan-mvp.md](plan-mvp.md).

| Hito | Para quién | Qué incluye |
|---|---|---|
| **MVP** | Solo tú | Funcionalidades marcadas MVP. Ya es multiusuario por dentro (RF-PLT-01), aunque haya un único usuario. |
| **Familia** | Tú y 2–3 familiares, por invitación | Requisitos marcados Familia (invitaciones, bienvenida, baja, privacidad, administración), plantillas de sus bancos, captura de pagos en Android si se valida y las funcionalidades F2 que más se hayan echado en falta usando el MVP. |
| **Futuro** | Registro abierto | No previsto. Los requisitos marcados Futuro quedan documentados por si algún día cambia. |

**MVP: "Saber dónde estoy"**
Cuentas con remuneración por tramos y depósitos · movimientos manuales e importación CSV/XLSX (plantillas de Bankinter y Cajamar) · Atajo de Apple Pay · categorías, reglas y transferencias · préstamos con cuadro de amortización · inversiones básicas (operaciones, FIFO, precio manual) · objetivos de ahorro · presupuestos en modo límites y base cero · panel de patrimonio y gastos · calculadoras de ahorro, vivienda, hipoteca, coche, préstamo y fondo de emergencia · PWA con inicio de sesión seguro · exportación y copias.

**F2: "Que entre solo"**
Norma 43 y OFX · plantillas del resto de bancos principales · reenvío de emails · precios y Euribor automáticos con fuentes gratuitas · detección de recurrentes y suscripciones · alertas push · previsión de saldo · rentabilidad XIRR/TWR · resumen fiscal · hogares compartidos · calculadoras avanzadas.

**F3: "Que me ayude a decidir"**
Informes exportables · simulación fiscal · estrategias de deuda · app nativa si hace falta.

**Aplazado (D12)**
Todo lo que depende de IA: lectura de tickets y PDF, preguntas en lenguaje natural, análisis automáticos y categorización inteligente.

---

## 8. Fuera de alcance

- Iniciar pagos o mover dinero (la plataforma es de solo lectura).
- Agregación bancaria por open banking, por ahora (ver 4.2).
- Monetización y servicios de pago: es gratuita y no se contrata nada aparte de la VPS.
- Apertura al público general: no prevista (requisitos "Futuro").
- Otros países e idiomas: solo España y en español.
- Funciones de IA, de momento (D12).
- Migración de histórico desde otras herramientas (D14).
- Asesoramiento financiero personalizado o recomendación de productos concretos: las calculadoras simulan, no aconsejan.
- Presentar la declaración de la renta (solo resumen orientativo).
- Contabilidad de autónomo o empresa (facturación, IVA trimestral) (D13).

---

## 9. Decisiones

### 9.1 Tomadas

| ID | Decisión | Fecha |
|---|---|---|
| D1 | Multiusuario desde el diseño (usuarios reales: ver D8). | 14/10/2026 |
| D2 | Los movimientos entran por alta manual, Atajo de Apple Pay e importación de extractos (CSV/XLSX en el MVP, Norma 43 en F2). Sin open banking por ahora. | 14/10/2026 |
| D3 | iPhone: PWA primero; app nativa (React Native + Expo compilada en la nube) solo si hace falta. | 14/10/2026 |
| D4 | Presupuestos: cada usuario elige entre límites por categoría y base cero; ambos modos en el MVP. | 14/10/2026 |
| D5 | Lanzamiento por etapas: uso propio → familia por invitación. El público no está previsto (D8). | 14/10/2026 |
| D6 | Producto gratuito, sin planes ni pagos. | 14/10/2026 |
| D7 | Mercado: solo España, interfaz en español. Las calculadoras cubren todas las comunidades autónomas. | 14/10/2026 |
| D8 | Usuarios: tú y 2–3 familiares cercanos. (P12) | 14/10/2026 |
| D9 | Importación válida para cualquier banco español con el importador genérico; plantillas predefinidas primero para Bankinter y Cajamar y después para los bancos principales. (P2) | 14/10/2026 |
| D10 | Alojamiento en tu VPS de netcup (VPS Lite 1 G12s). (P6) | 14/10/2026 |
| D11 | Coste cero: ningún servicio de pago; precios de inversiones con fuentes gratuitas o a mano. (P13) | 14/10/2026 |
| D12 | Sin funciones de IA de momento. (P8) | 14/10/2026 |
| D13 | Sin contabilidad de autónomo. (P7) | 14/10/2026 |
| D14 | Sin migración de histórico. (P9) | 14/10/2026 |
| D15 | Titular del servicio: tú, como persona física. (P14) | 14/10/2026 |
| D16 | Tecnologías: las que ya conoces (React, Astro, Node, Django, FastAPI, Flask, MySQL/PostgreSQL). (P11) | 14/10/2026 |
| D17 | Arquitectura: FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL y React + TypeScript como PWA; autenticación propia y panel con SQLAdmin. Detalle en §10. (P15) | 14/10/2026 |
| D18 | Dirección: `miahorro.octogas.es`, subdominio de tu dominio en DonDominio, en la misma VPS donde está octogas.es en producción, sin afectarla (RNF-18). (P16, P17) | 14/10/2026 |
| D19 | Familia con iPhone (mayoría) y Android. En iPhone, Atajo de Apple Pay; en Android, alta manual e importación, con la captura por notificaciones como opción a validar (RF-MOV-17). (P18) | 14/10/2026 |
| D20 | Sin open banking, ni siquiera para tus cuentas, para que tu uso sea igual que el de tus familiares. (P19) | 14/10/2026 |
| D21 | Alcance del MVP aprobado tal como está en §7. (P20) | 14/10/2026 |
| D22 | Registro abierto en lugar de invitaciones, para poder pasar la app a amigos sin gestionar altas. Sustituye a la parte de D8 que limitaba el alta a invitaciones. El primer usuario es el administrador; hay tope de usuarios e interruptor para cerrar el registro. Consecuencia: puede haber usuarios fuera de la familia, así que el texto de privacidad (RF-PLT-06) gana importancia. | 16/10/2026 |
| D23 | Face ID primero: en el alta se ofrece crear una passkey (un toque) y, como alternativa, la app de códigos. Tras una contraseña, la passkey vale como segundo factor. Con passkey, los códigos de recuperación pasan a ser opcionales. Si alguien pierde el acceso sin códigos, el administrador lo resuelve con `reset-mfa`. | 16/10/2026 |
| D24 | Se adelanta la importación de extractos PDF (RF-IMP-03) para Bankinter y Cajamar, porque es el formato que se consigue con facilidad. Cada banco tiene su propio lector, sin IA: solo PDF digitales (no escaneados), y solo se acepta el extracto si cada saldo cuadra con el anterior más el importe; si no, no se importa nada. El signo de cada importe sale del cambio de saldo. | 16/10/2026 |
| D25 | El saldo inicial de una cuenta es un ancla: lo que había al empezar su fecha. Los movimientos desde esa fecha mueven el saldo; los anteriores (historial importado) ya están dentro y solo sirven para conocer saldos pasados, que se calculan hacia atrás. Así se puede crear la cuenta con el saldo de hoy e importar meses anteriores sin descuadrarla. | 16/10/2026 |
| D26 | Presupuesto: los dos modos guardan lo mismo (lo puesto en cada categoría y mes), así que cambiar de modo no pierde nada. En límites, un tope se mantiene hasta que se cambia; en base cero se asigna cada mes y el saldo de cada categoría siempre se arrastra. «Por asignar» = dinero de las cuentas del día a día (corriente, ahorro, efectivo, monedero y tarjeta) menos lo apartado para objetivos menos lo que tienen las categorías. La línea de una categoría principal incluye sus subcategorías salvo las que tengan línea propia. | 19/10/2026 |
| D27 | Calculadoras: se calculan en el servidor con decimales exactos y un escenario guardado conserva solo los datos de entrada, así que al abrirlo se recalcula con los valores vigentes. Las tablas de referencia (ITP y AJD por comunidad, IVA o IGIC de la vivienda nueva, escala del ahorro, impuesto de matriculación y gastos de compraventa estimados) tienen fecha de vigencia y fuente, se editan en `/admin` y sus valores iniciales se cargan al arrancar sin pisar lo editado; un cambio es una fila nueva con su fecha. Las escalas progresivas del ITP se aplican por tramos, y se puede indicar un tipo reducido propio (jóvenes, familia numerosa…), porque cada comunidad tiene sus requisitos. Los límites de comisión de la Ley 5/2019 y la Ley 16/2011 siguen en el código: son ley estatal estable y están cubiertos por tests. La TAE usa la fórmula oficial de la Ley 16/2011. | 20/10/2026 |
| D28 | Inversiones: una inversión por ISIN aunque esté en varios bancos, porque Hacienda aplica FIFO a todos los valores homogéneos juntos. Las compras incluyen su comisión en el coste y las ventas descuentan la suya; los traspasos entre fondos (y entre planes de pensiones) conservan fecha y coste y no generan ganancia; los rescates de planes de pensiones no van a la base del ahorro. Si una venta con pérdidas tiene una recompra cerca (dos meses en valores cotizados, un año en fondos), se avisa de que puede no ser compensable (art. 33.5 LIRPF), sin calcular el diferimiento. Comprar o vender mueve dinero sin ser gasto ni ingreso: el movimiento de la cuenta es de tipo «inversión» y se concilia con el del extracto del banco; un dividendo sí es ingreso y una comisión suelta, gasto. El precio es el último entre los introducidos a mano y el de la última compra o venta. Los importes van en euros, como en el informe fiscal del bróker. | 21/10/2026 |
| D29 | Panel e informes: el patrimonio neto es cuentas + inversiones con precio + lo que te deben − el capital pendiente de tus préstamos, en la divisa principal (las cuentas en otras divisas se muestran aparte, sin convertir). Cada cuenta cuenta desde el primer día del que hay datos (su fecha de apertura o su movimiento más antiguo) y cada préstamo desde su firma; la vivienda y el coche no son activos hasta que lleguen los bienes (RF-INV-09). La evolución se calcula a fin de cada mes, sin guardar nada. Los gastos se comparan con el periodo anterior y con las mismas fechas un año antes; un mes en curso se compara con los mismos días del anterior. El comercio sale del concepto del movimiento con la misma limpieza que las reglas. La exportación es un JSON con importes exactos y un ZIP con un CSV por tabla para hoja de cálculo; nunca incluye secretos. | 21/10/2026 |

### 9.2 Preguntas abiertas

Ninguna: la definición funcional está cerrada.

**Pendiente para el despliegue (no afecta al alcance):** saber qué servidor web o proxy inverso sirve octogas.es (Nginx, Apache, Caddy, Traefik…) y si corre en Docker, para integrar el subdominio tocando lo mínimo su configuración.

---

## 10. Arquitectura técnica (D17)

**Decisión D17:** backend con **FastAPI**. Lo que Django habría dado hecho (panel de administración, autenticación, migraciones) se cubre con las piezas de esta tabla.

| Pieza | Elección | Notas |
|---|---|---|
| Backend y API | **FastAPI** + Pydantic v2 | Esquemas tipados y documentación OpenAPI automática. |
| Acceso a datos | **SQLAlchemy 2** + **Alembic** (migraciones) | Columnas `Numeric` con `Decimal` para los importes (RNF-04). Endpoints síncronos: con 3 usuarios la asincronía no aporta nada y así se evitan las trampas de SQLAlchemy asíncrono. |
| Base de datos | **PostgreSQL** | Tipo `numeric` exacto, robusta y ya la conoces. |
| Autenticación | Módulo propio sobre librerías probadas: **pwdlib** (contraseñas con Argon2), **pyotp** (segundo factor), **webauthn** (passkeys) y sesiones en cookie `HttpOnly` guardadas en PostgreSQL | El alcance es pequeño porque no hay registro abierto, solo invitaciones. Se descarta fastapi-users porque está en modo mantenimiento (solo recibe correcciones de seguridad). Al ser la parte más delicada, lleva tests propios y protección CSRF y frente a fuerza bruta (RNF-05). |
| Panel de administración | **SQLAdmin** | Panel sobre los modelos de SQLAlchemy con su propio control de acceso. Solo se registran usuarios, invitaciones, tablas de referencia y plantillas de importación; nunca los datos financieros (RF-PLT-08). |
| Cálculos financieros | Paquete Python propio, independiente de FastAPI, con tests exhaustivos (RNF-10) | Una única implementación de amortización, intereses, FIFO y calculadoras. Las calculadoras del frontend llaman a la API, así que la lógica no se duplica en dos lenguajes. |
| Cliente de la API en React | Generado automáticamente desde el OpenAPI de FastAPI | Los tipos de TypeScript salen del backend, lo que compensa en buena parte no usar un único lenguaje. Los importes viajan como texto y el frontend los maneja con una librería decimal. |
| Frontend | **React** + TypeScript con Vite, como PWA | Aplicación rápida en el móvil; *service worker* para instalarla, recibir notificaciones push y funcionar sin conexión (RNF-02). |
| Importación de extractos | Módulo `csv` estándar + **openpyxl** para XLSX | Ligero; pandas no hace falta con este volumen. |
| Tareas programadas | Comandos de línea (Typer) lanzados por cron | Euribor, precios, recurrentes y alertas son pocas tareas y de poco volumen; no hace falta Celery ni Redis. |
| Notificaciones | Web Push con claves propias (VAPID) mediante **pywebpush** | Gratis y sin depender de Firebase. |
| Servidor web | Uvicorn detrás del proxy inverso que ya sirve octogas.es, añadiendo un host virtual para `miahorro.octogas.es` con su certificado de Let's Encrypt | Sin un segundo servidor web compitiendo por los puertos 80/443 (RNF-18). Caddy solo si el proxy actual no permitiera integrarlo. |
| Despliegue | Docker Compose en la VPS, separado de octogas.es y con límites de recursos | Reproducible, fácil de restaurar en otra máquina y sin riesgo para producción (RNF-18). |
| Copias | `pg_dump` diario cifrado a un almacenamiento externo gratuito, además de los snapshots de netcup | RNF-07. |
| Web pública | Astro | Solo si algún día se abre al público (Futuro). |

Con este volumen, PostgreSQL, la API y Caddy juntos deberían quedarse por debajo de 1 GB de RAM, así que caben con holgura en la VPS.

**Qué supone FastAPI frente a Django:** más trabajo inicial en autenticación, invitaciones y configuración del panel de administración. A cambio, la API queda tipada de extremo a extremo, el cliente de React se genera solo y el framework es el que prefieres mantener.

**Alternativas descartadas**

- **Django:** lo trae casi todo hecho, pero prefieres FastAPI.
- **Node full-stack (Next.js o similar):** un único lenguaje, pero sin un panel de administración ni una autenticación tan completos de serie, y los importes exactos requieren librerías aparte.
- **Flask:** igual de manual que FastAPI, con menos ventajas.
- **Proveedor de identidad autoalojado (Keycloak, Authentik):** resolvería la autenticación, pero pide bastante memoria (del orden de 1–2 GB) y es excesivo para 3 usuarios.

**Material necesario durante el desarrollo**

- Un extracto de ejemplo de Bankinter y otro de Cajamar (CSV o XLSX, con los datos anonimizados) para crear sus plantillas.
- Registro DNS `A` (y `AAAA` si la VPS tiene IPv6) de `miahorro.octogas.es` apuntando a la VPS, creado en el panel de DonDominio.
- Qué servidor web o proxy usa octogas.es y cómo está desplegado (ver 9.2).

---

## 11. Referencias

**Aplicaciones de las que tomar ideas:** Fintonic (agregación bancaria en España), YNAB (presupuesto base cero), Monarch y Copilot (experiencia de usuario). De código abierto: Firefly III (reglas e importador compatible con Enable Banking), Actual Budget (presupuestos) y Ghostfolio (seguimiento de inversiones).

**Fuentes consultadas**

- Enable Banking, modo restringido para cuentas propias: https://enablebanking.com/docs/api/linked-accounts/
- Estado de GoCardless Bank Account Data (fuente secundaria): https://dev.to/johnfrandsen/gocardless-bank-account-data-alternatives-what-to-use-when-signups-are-disabled-326d
- Apple FinanceKit, países disponibles: https://developer.apple.com/documentation/financekit
- Automatización de Atajos con Apple Pay: https://www.idropnews.com/ios-17/this-new-ios-17-shortcut-will-help-you-keep-track-of-your-spending/197589/
- Compilar apps iOS sin Mac con Expo: https://expo.dev/articles/testing-and-previewing/test-ios-app-without-mac
- netcup VPS Lite, características: https://www.netcup.com/en/server/vps-lite

---

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 14/10/2026 | Primer borrador: catálogo de funcionalidades, integraciones, opciones de iPhone y preguntas abiertas. |
| 0.2 | 14/10/2026 | Decisiones D1–D7: producto gratuito para terceros en España, sin open banking, PWA, dos modos de presupuesto. Nuevo módulo de plataforma multiusuario (PLT), RNF de RGPD y escalabilidad, hitos de lanzamiento. |
| 0.3 | 14/10/2026 | Decisiones D8–D16: tú y 2–3 familiares, VPS netcup, coste cero, sin IA, sin histórico, sin autónomo. Hitos Beta/Público sustituidos por Familia/Futuro; PLT y RGPD simplificados; plantillas de Bankinter y Cajamar en el MVP; propuesta técnica (§10). |
| 0.4 | 14/10/2026 | D17: backend con FastAPI en lugar de Django. §10 rehecho: autenticación propia (pwdlib, pyotp, webauthn), SQLAdmin, SQLAlchemy 2 + Alembic, cálculos financieros en un único paquete Python y cliente React generado desde OpenAPI. |
| 1.0 | 14/10/2026 | Definición cerrada. D18–D21: subdominio `miahorro.octogas.es` en la VPS compartida con octogas.es (RNF-18), familia mixta iPhone/Android (RF-MOV-17), sin open banking, MVP aprobado. |
| 1.1 | 16/10/2026 | D22: registro abierto con salvaguardas (RF-PLT-03 pasa al MVP; RF-PLT-10 actualizado). D23: Face ID como método principal (RF-USR-01). |
| 1.2 | 16/10/2026 | D24: extractos PDF de Bankinter y Cajamar en el MVP (RF-IMP-03), con comprobación de saldos. D25: el saldo inicial es un ancla en su fecha. Saldo tras cada movimiento (RF-MOV-15) e informes por mes, año o fechas a elegir (RF-INF-03). El lector de Cajamar queda pendiente hasta tener un extracto de ejemplo. |
| 1.3 | 16/10/2026 | RF-MOV-07: reglas que convierten un movimiento en transferencia entre cuentas propias. |
| 1.4 | 19/10/2026 | D26: cómo funcionan los dos modos de presupuesto y «Por asignar». |
| 1.5 | 20/10/2026 | D27: calculadoras, escenarios y tablas de referencia con vigencia y fuente. |
| 1.6 | 21/10/2026 | D28: inversiones con FIFO, traspasos, planes de pensiones y movimientos de tipo inversión. |
| 1.7 | 21/10/2026 | D29: patrimonio neto, informes con comparación y exportación de datos. |
