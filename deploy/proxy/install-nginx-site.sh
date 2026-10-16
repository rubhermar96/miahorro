#!/usr/bin/env bash
# Add miahorro.octogas.es to the VPS's nginx without touching any other site (RNF-18).
#   - backs up /etc/nginx first
#   - only adds a new site file; if `nginx -t` fails it removes it again and nginx is not reloaded
#   - reloads nginx (never restarts it), so octogas.es keeps serving throughout
#   - then asks certbot for the HTTPS certificate
# Run on the VPS from the repository:  ./deploy/proxy/install-nginx-site.sh
set -euo pipefail
cd "$(dirname "$0")"

domain=miahorro.octogas.es
port=$(grep '^MIAHORRO_HTTP_PORT=' ../.env 2>/dev/null | cut -d= -f2- || true)
port=${port:-8090}

# Debian/Ubuntu layout (sites-available + sites-enabled) or a plain conf.d directory.
if [[ -d /etc/nginx/sites-enabled ]]; then
  site=/etc/nginx/sites-available/$domain
  link=/etc/nginx/sites-enabled/$domain
else
  site=/etc/nginx/conf.d/$domain.conf
  link=
fi

if [[ -e "$site" || ( -n "$link" && -e "$link" ) ]]; then
  echo "Ya existe la configuración de $domain ($site); no se toca nada." >&2
  exit 1
fi

if ! getent hosts "$domain" >/dev/null; then
  echo "$domain todavía no resuelve en DNS. Crea el registro A en DonDominio y vuelve a intentarlo." >&2
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null; then
  echo "MiAhorro no responde en 127.0.0.1:$port. Arráncalo antes con ./deploy/deploy.sh" >&2
  exit 1
fi

backup=/etc/nginx.bak-$(date +%Y%m%d-%H%M%S)
sudo cp -a /etc/nginx "$backup"
echo "Copia de la configuración de nginx en $backup"

sed "s|127.0.0.1:8090|127.0.0.1:$port|" nginx.conf | sudo tee "$site" >/dev/null
[[ -n "$link" ]] && sudo ln -s "$site" "$link"

if ! sudo nginx -t; then
  sudo rm -f "$site" ${link:+"$link"}
  echo "La configuración no es válida: se ha retirado y nginx NO se ha recargado." >&2
  exit 1
fi
sudo systemctl reload nginx
echo "Sitio activo por HTTP: http://$domain"

if command -v certbot >/dev/null; then
  sudo certbot --nginx -d "$domain"
  sudo nginx -t && sudo systemctl reload nginx
  echo "Listo: https://$domain"
else
  echo "certbot no está instalado. Instálalo (sudo apt install certbot python3-certbot-nginx)"
  echo "y ejecuta: sudo certbot --nginx -d $domain"
fi
