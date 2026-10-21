# Despliegue de MiAhorro en la VPS

MiAhorro se publica en `https://miahorro.octogas.es`, en la misma VPS que octogas.es, **sin tocar sus servicios** (RNF-18):

```
Internet ──HTTPS──▶ nginx de la VPS (el de octogas.es, instalado en el sistema)
                      ├─ octogas.es            ─▶ (sin cambios)
                      └─ miahorro.octogas.es   ─▶ 127.0.0.1:8090 ─▶ contenedor web (Caddy)
                                                                      ├─ /api, /admin ─▶ api (FastAPI)
                                                                      └─ resto        ─▶ app (PWA)
                                                                     api ─▶ db (PostgreSQL)
```

- Los tres contenedores de MiAhorro tienen su propia red, su propio volumen de datos y límites de memoria y CPU.
- El único puerto publicado escucha solo en `127.0.0.1`, de modo que únicamente el proxy de la VPS puede llegar a él.
- En el nginx de octogas.es solo se **añade** un sitio nuevo; nginx se recarga, nunca se reinicia.

## 1. Lo que hace falta en la VPS

Docker con el plugin Compose, `git`, `gpg`, `openssl`, `curl`, `certbot` con su plugin de nginx y, para la copia externa, `rclone`.

```bash
docker compose version && git --version && gpg --version | head -1 && certbot --version && rclone version | head -1
```

Lo que falte se instala con `sudo apt install git gnupg certbot python3-certbot-nginx rclone`. Docker se instala con la [guía oficial](https://docs.docker.com/engine/install/).

## 2. Registro DNS (DonDominio)

En el panel de DonDominio, zona DNS de `octogas.es`:

- Registro `A`: `miahorro` → la IPv4 de la VPS.
- Registro `AAAA`: `miahorro` → la IPv6 de la VPS, solo si octogas.es también usa IPv6.

Comprobación (puede tardar unos minutos en propagarse):

```bash
dig +short miahorro.octogas.es
```

## 3. Código y secretos

```bash
# Clave de solo lectura para que la VPS pueda descargar el repositorio privado
ssh-keygen -t ed25519 -f ~/.ssh/miahorro_deploy -N "" -C "miahorro-deploy"
cat ~/.ssh/miahorro_deploy.pub   # añadirla en GitHub: Settings → Deploy keys (sin permiso de escritura)

sudo mkdir -p /opt/miahorro && sudo chown "$USER" /opt/miahorro
GIT_SSH_COMMAND="ssh -i ~/.ssh/miahorro_deploy" git clone git@github.com:<usuario>/miahorro.git /opt/miahorro
git -C /opt/miahorro config core.sshCommand "ssh -i ~/.ssh/miahorro_deploy"

cd /opt/miahorro/deploy
./init-env.sh    # genera deploy/.env y la clave de las copias: guárdalas en tu gestor de contraseñas
```

Si el puerto `8090` ya está ocupado en la VPS, cambia `MIAHORRO_HTTP_PORT` en `deploy/.env` y en la configuración del proxy.

## 4. Antes de tocar nada: foto de octogas.es

```bash
./check-octogas.sh > /tmp/octogas-antes.txt
```

## 5. Primer arranque

```bash
./deploy.sh
curl -s http://127.0.0.1:8090/api/health   # {"status":"ok",...}
```

**Importante:** la primera cuenta que se registra es la de administrador. Regístrate tú en cuanto la app esté accesible (paso 7).

## 6. nginx y HTTPS

```bash
./proxy/install-nginx-site.sh
```

El script hace lo siguiente:

1. Comprueba que `miahorro.octogas.es` ya resuelve en DNS y que MiAhorro responde en `127.0.0.1:8090`.
2. Copia `/etc/nginx` entera a `/etc/nginx.bak-<fecha>`.
3. Añade solo el sitio nuevo (`proxy/nginx.conf`) y lo valida con `nginx -t`. Si la validación falla, retira el sitio y no recarga nada.
4. Recarga nginx; octogas.es no se interrumpe.
5. Pide el certificado con certbot, que también añade la redirección de HTTP a HTTPS.

Si después algo fuera mal, esto deja nginx como estaba:

```bash
sudo rm /etc/nginx/sites-enabled/miahorro.octogas.es && sudo nginx -t && sudo systemctl reload nginx
```

## 7. Comprobación final

```bash
./check-octogas.sh > /tmp/octogas-despues.txt
diff /tmp/octogas-antes.txt /tmp/octogas-despues.txt   # solo debe aparecer la línea de los contenedores de MiAhorro
```

Después, en el iPhone:

1. Abre `https://miahorro.octogas.es` en Safari → Compartir → **Añadir a pantalla de inicio**.
2. Abre la app desde el icono y pulsa **Crear una** para registrarte; serás el administrador.
3. Elige **Usar Face ID**. A partir de ahí entrarás con un toque.
4. Opcional, pero recomendable: en **Más → Seguridad**, crea los códigos de recuperación y guárdalos con el botón **Guardar**.

Para entrar desde un ordenador: pulsa «Entrar con Face ID o passkey» y elige usar un teléfono. Escaneas el código QR con el iPhone y confirmas con Face ID (el ordenador necesita Bluetooth). Otra opción es añadir en ese ordenador su propia passkey (Windows Hello) desde **Más → Seguridad**.

## Gestión de usuarios

```bash
cd /opt/miahorro/deploy
alias miahorro='docker compose -f compose.prod.yaml exec api python -m app.cli'
miahorro list-users
miahorro create-user --email familiar@email.com --name "Nombre"   # alta manual (opcional: también pueden registrarse en la app)
miahorro reset-mfa --email tu@email.com      # móvil perdido sin códigos: quita 2FA y passkeys
miahorro set-password --email tu@email.com   # contraseña olvidada
```

El panel `https://miahorro.octogas.es/admin` (solo administradores) permite ver los usuarios y desactivarlos.

**Registro abierto.** Cualquiera que tenga la dirección puede crearse una cuenta, hasta un máximo de 20 (`MIAHORRO_MAX_USERS`). Para cerrarlo, pon `MIAHORRO_REGISTRATION_ENABLED=false` en `deploy/.env` y ejecuta `./deploy.sh`. Las cuentas existentes siguen funcionando.

## 8. Copias de seguridad

1. **Copia externa (opcional, recomendada):** configura un remoto de rclone hacia un almacenamiento que ya tengas, como Google Drive u OneDrive. Usa una carpeta dedicada, porque en ella se borran las copias con más de 30 días.

   ```bash
   rclone config                     # crear el remoto, p. ej. "gdrive"
   rclone mkdir gdrive:miahorro-backups
   ```

   Después pon `BACKUP_RCLONE_REMOTE=gdrive:miahorro-backups` en `deploy/.env`.

2. **Programarlas cada día:**

   ```bash
   sudo touch /var/log/miahorro-backup.log && sudo chown "$USER" /var/log/miahorro-backup.log
   (crontab -l 2>/dev/null; echo "30 3 * * * /opt/miahorro/deploy/backup.sh >> /var/log/miahorro-backup.log 2>&1") | crontab -
   ```

3. **Simulacro de restauración** (no toca producción):

   ```bash
   ./backup.sh
   ./restore.sh --check "$(ls -t /var/backups/miahorro/*.dump.gpg | head -1)"
   ```

   Para probar también la copia externa, descárgala primero con `rclone copy gdrive:miahorro-backups/<fichero> /tmp/` y pasa ese fichero a `restore.sh --check`.

Restaurar de verdad, reemplazando los datos actuales: `./restore.sh <copia.dump.gpg>`. Antes de hacerlo, el script guarda una copia del estado actual.

### Simulacro en otra máquina

Comprueba que una copia sirve para levantar MiAhorro desde cero, en cualquier ordenador con Docker, `gpg` y este repositorio (en Windows, desde Git Bash). No toca producción ni deja nada instalado.

```bash
# 1. En la VPS: el resumen de producción y una copia recién hecha
docker compose -f compose.prod.yaml exec api python -m app.cli summary > /tmp/resumen-produccion.txt
./backup.sh

# 2. Llévate la copia (.dump.gpg), el resumen y la clave de las copias (del gestor de contraseñas)
# 3. En la otra máquina, desde la raíz del repositorio:
./deploy/restore-elsewhere.sh miahorro-<fecha>.dump.gpg clave-copias.txt > resumen-restaurado.txt
diff <(sed -n '/^Tablas/,/^Simulacro/p' resumen-restaurado.txt | sed '/^$/d;/^Simulacro/d') resumen-produccion.txt
```

El script restaura en una base temporal, aplica las migraciones del código actual (así se comprueba también que la copia sirve para la versión nueva) y muestra el mismo resumen: filas por tabla y, por usuario, movimientos, saldos y patrimonio. Si `diff` no muestra nada, todo cuadra.

## Atajo de Apple Pay compartido

Los pasos para crearlo están en [docs/uso.md](../docs/uso.md#atajo-compartido-solo-el-administrador-una-vez). Cuando tengas el enlace de iCloud:

```bash
# deploy/.env
MIAHORRO_SHORTCUT_URL=https://www.icloud.com/shortcuts/...
./deploy.sh
```

## Comprobaciones

```bash
curl -s http://127.0.0.1:8090/api/health                                     # {"status":"ok","database":"ok",...}
docker compose -f compose.prod.yaml logs --tail 100 api                       # errores recientes
docker compose -f compose.prod.yaml exec api python -m app.cli summary         # datos por usuario
docker compose -f compose.prod.yaml exec api python -m app.cli sync-reference-values  # tablas de referencia
```

## Despliegues siguientes

```bash
cd /opt/miahorro/deploy && ./deploy.sh
```

El script actualiza el código, hace una copia de seguridad, reconstruye, aplica las migraciones y comprueba que la API responde.
