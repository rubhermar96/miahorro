# Guía de uso de MiAhorro

MiAhorro reúne tus cuentas, gastos, préstamos, inversiones y objetivos en una app que se instala en el iPhone. Esta guía cuenta qué hace cada pantalla y cómo sacarle partido sin apuntar casi nada a mano.

## Empezar

1. Abre la dirección de MiAhorro en Safari → **Compartir → Añadir a pantalla de inicio**. Desde entonces se abre como una app.
2. Crea tu cuenta y elige **Usar Face ID**. Para entrar desde un ordenador: «Entrar con Face ID o passkey» y escanea el código con el iPhone.
3. En **Más → Seguridad** crea los códigos de recuperación y guárdalos: sirven si pierdes el móvil.
4. Da de alta tus cuentas con el saldo de hoy (**Inicio → Añadir cuenta**). El saldo inicial es el punto de partida: lo que importes de antes no lo descuadra.

## Inicio: el panel

- **Patrimonio neto:** cuentas + inversiones + lo que te deben − lo que queda de tus préstamos, y cuánto ha cambiado desde fin del mes pasado. «Ver evolución e informes» lleva al detalle.
- **Disponible:** el dinero de las cuentas del día a día, sin lo apartado para objetivos.
- **Ahorrado este mes:** ingresos menos gastos del mes financiero (empieza el día que elijas en **Más → Preferencias**, normalmente el de la nómina).
- Debajo: presupuesto, objetivos, próximos cargos (recibos y cuotas de préstamos), vencimientos, cuentas e inversiones.

## Apuntar movimientos

- **Botón +:** importe, categoría y Guardar. Las categorías que más usas salen primero.
- **Sin conexión:** si no hay cobertura, el gasto se queda guardado en el móvil y se envía solo al volver la conexión. Un aviso arriba dice cuántos quedan pendientes.
- **Transferencias** entre tus cuentas: no cuentan como gasto ni ingreso.
- **Importar extractos** (**Más → Importar**): CSV, Excel o el PDF de Bankinter. MiAhorro reconoce las columnas, detecta lo ya importado y une lo que apuntaste a mano o capturó Apple Pay, sin duplicar. Se puede deshacer una importación entera.
- **Reglas** (**Más → Reglas**): «si el concepto contiene MERCADONA → Supermercado». Al corregir una categoría a mano, la app te propone crear la regla.

## Apple Pay: pagos al momento

En **Más → Captura de pagos** conectas el iPhone:

1. **Conectar un iPhone** → elige la cuenta por defecto.
2. **Copiar mi código** e **Instalar el Atajo**: al instalarlo, el Atajo pide ese código.
3. En la app **Atajos → Automatización → Nueva → Transacción**: elige tus tarjetas, marca «Ejecutar inmediatamente», y añade **Ejecutar atajo → MiAhorro**.

Cada pago aparece en segundos como **pendiente**; cuando importas el extracto, se une con el movimiento del banco. Si pierdes el móvil, **Desconectar** anula su código. Cada tarjeta de la Cartera puede ir a una cuenta distinta.

## Revisar y recurrentes

- **Revisar** (aviso en Inicio): pagos capturados que el banco nunca confirmó y recibos que no han llegado.
- **Más → Recurrentes:** nómina, alquiler, suscripciones… La app avisa de los próximos y los marca como cumplidos al llegar el movimiento real.

## Planificar

- **Presupuesto:** por límites (un tope por categoría) o base cero (asignas cada euro). Cambiar de modo no pierde nada.
- **Objetivos:** dinero apartado dentro de tus cuentas (huchas) o cuentas enteras. Te dice cuánto ahorrar al mes y cuándo llegarás a tu ritmo.
- **Préstamos e hipotecas:** cuadro de amortización, Euribor, simulación de amortizar antes (con la comisión máxima legal) y lo que te queda por pagar.
- **Calculadoras:** interés compuesto, meta de ahorro, fondo de emergencia, compra de vivienda (ITP o IVA + AJD de tu comunidad), hipoteca, coche y préstamo personal. Se precargan con tus datos, se guardan como escenarios y se comparan lado a lado. Los resultados son orientativos.

## Inversiones

- Da de alta fondos, ETF, acciones y planes de pensiones (mejor con su ISIN).
- Apunta compras, ventas, dividendos, comisiones, splits y traspasos entre fondos. Si eliges la cuenta de cargo, el movimiento se apunta allí y se concilia con el extracto.
- Actualiza el precio de vez en cuando (valor liquidativo): la app avisa si tiene más de un mes.
- **Informe fiscal:** las ventas del año por FIFO, lote a lote, como las pide Hacienda, para compararlas con el informe de tu banco o bróker.

## Informes

- **Patrimonio:** evolución a fin de cada mes, con su tabla.
- **Ingresos y gastos:** por mes, por año o entre fechas, con la tasa de ahorro frente a tu objetivo.
- **Gastos:** por categoría, comercio o etiqueta, comparados con el periodo anterior y con las mismas fechas del año pasado.

## Tus datos

- **Más → Exportar mis datos:** todo en JSON (importes exactos) o en CSV para hoja de cálculo.
- Cada persona solo ve lo suyo. Al cerrar sesión se borra lo guardado para usar sin conexión.

## Atajo compartido (solo el administrador, una vez)

El Atajo se crea una sola vez y se comparte por enlace; cada persona solo pone su código.

1. En la app **Atajos**, crea un atajo nuevo llamado **MiAhorro** que reciba transacciones como entrada.
2. Acción **Texto** con el contenido `CODIGO`; en los detalles del atajo, añade una **pregunta de importación** sobre ese texto: «Pega tu código de MiAhorro».
3. Acción **Obtener contenido de URL**:
   - URL: `https://miahorro.octogas.es/api/capture/payments`, método **POST**.
   - Encabezado `Authorization` con el valor `Bearer ` seguido de la variable del texto anterior.
   - Cuerpo JSON con `amount` (importe), `merchant` (comercio) y `card` (tarjeta) de la transacción.
4. Opcional: **Mostrar notificación** con el campo `message` de la respuesta.
5. Prueba que funciona con tu propio código y comparte el atajo: **Compartir → Copiar enlace de iCloud**.
6. Pon ese enlace en `MIAHORRO_SHORTCUT_URL` en `deploy/.env` y ejecuta `./deploy.sh`. Desde entonces, **Captura de pagos** muestra «Instalar el Atajo» en vez de la guía manual.
