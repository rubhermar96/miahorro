# Despliegue de MiAhorro en la VPS

MiAhorro se publica en `https://miahorro.octogas.es`, en la misma VPS que octogas.es, **sin tocar sus servicios** (RNF-18):

```
Internet ──HTTPS──▶ proxy actual de la VPS (el de octogas.es)
                      ├─ octogas.es            ─▶ (sin cambios)
                      └─ miahorro.octogas.es   ─▶ 127.0.0.1:8090 ─▶ contenedor web (Caddy)
                                                                      ├─ /api, /admin ─▶ api (FastAPI)
                                                                      └─ resto        ─▶ app (PWA)
                                                                     api ─▶ db (PostgreSQL)
```

- Los tres contenedores de MiAhorro tienen su propia red, su propio volumen de datos y límites de memoria y CPU.
- El único puerto publicado escucha solo en `127.0.0.1`, de modo que únicamente el proxy de la VPS puede llegar a él.
- En el proxy de octogas.es solo se **añade** un host virtual; se recarga, nunca se reinicia.

## 1. Lo que hace falta en la VPS

Docker con el plugin Compose, `git`, `gpg`, `openssl`, `curl` y, para la copia externa, `rclone`.

```bash
docker compose version && git --version && gpg --version | head -1 && rclone version | head -1
```

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

## 6. Proxy y HTTPS

Usa la plantilla de `proxy/` que corresponda al servidor web de la VPS y sigue las instrucciones de su cabecera:

| Servidor web | Plantilla |
|---|---|
| nginx | `proxy/nginx.conf` |
| Apache | `proxy/apache.conf` |
| Caddy | `proxy/Caddyfile.snippet` |

Antes de editar nada, haz una copia de la configuración actual del proxy (por ejemplo `sudo cp -a /etc/nginx /etc/nginx.bak-$(date +%F)`).

Si el proxy de la VPS corre **dentro de Docker**, no puede llegar a `127.0.0.1:8090` del anfitrión. En ese caso se conecta el contenedor `web` de MiAhorro a la red de ese proxy; lo adaptamos cuando sepamos cuál es.

## 7. Comprobación final

```bash
./check-octogas.sh > /tmp/octogas-despues.txt
diff /tmp/octogas-antes.txt /tmp/octogas-despues.txt   # solo debe aparecer la línea de los contenedores de MiAhorro
```

Después, en el iPhone: abre `https://miahorro.octogas.es` en Safari → Compartir → **Añadir a pantalla de inicio**.

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

## Despliegues siguientes

```bash
cd /opt/miahorro/deploy && ./deploy.sh
```

El script actualiza el código, hace una copia de seguridad, reconstruye, aplica las migraciones y comprueba que la API responde.
