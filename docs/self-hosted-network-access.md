# Store network and remote access

## Default: LAN-only POS access

The default deployment exposes only TCP 443 on the store server's explicitly configured LAN IPv4 address. SQL Server, Redis, Gunicorn, and Caddy's remote-access origin are not published on a LAN interface. The additional Caddy origin is published on host loopback only at `127.0.0.1:8080`.

1. Give the store server a DHCP reservation or static LAN address.
2. Create a local DNS record (recommended) such as `retailo.lan` pointing to that LAN address. If the router has no local DNS, add a hosts-file entry on each managed POS device.
3. Set `LAN_BIND_IP` and `RETAILO_HOSTNAME` in `.env.prod`.
4. Permit TCP 443 from the store's trusted POS VLAN/subnet to the store server. Deny TCP 1433, 6379, 8000, and 8080 from all LAN clients.
5. Do not configure port forwarding, DMZ, UPnP, or public firewall rules on the router.

Example UFW policy (replace the subnet and interface values with the store's real network; do not blindly paste the sample):

```sh
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 443 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Restrict SSH to the administrator subnet or management VLAN. If using a different firewall, implement equivalent source-restricted rules. Docker-published ports can interact with host firewall chains differently across distributions; verify from a second LAN device that only the intended listener is reachable.

## Local TLS for POS devices

Caddy uses its internal CA for `https://retailo.lan`. This provides HTTPS on the local network without purchasing a public domain.

1. Start the proxy and allow Caddy to initialize its CA.
2. Export only the CA root certificate from Caddy's persistent data volume:

   ```sh
   sudo docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T proxy cat /data/caddy/pki/authorities/local/root.crt > /tmp/retailo-local-root.crt
   ```

   Do not copy or distribute the CA private key.
3. Install the root certificate into the trusted root store of every managed POS browser/device. For a Linux POS:

   ```sh
   sudo install -m 0644 /tmp/retailo-local-root.crt /usr/local/share/ca-certificates/retailo-local.crt
   sudo update-ca-certificates
   ```

   For Windows, run an elevated terminal: `certutil -addstore -f Root retailo-local-root.crt`. For macOS: `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain retailo-local-root.crt`. Use the OS/browser vendor's managed certificate deployment for fleets.
4. Confirm the browser shows a valid certificate for the exact `RETAILO_HOSTNAME` and that login/session cookies work over HTTPS.
5. Keep the Caddy data volume in backups; losing it can require re-trusting a newly generated local CA.

If using a public domain instead, configure Caddy with a real domain and a valid certificate issuance method. DNS and certificate validation must be planned without opening router ports; a tunnel-based option is described below.

## Optional remote owner/support access with Tailscale

Tailscale runs on the store-server host, not as a cloud-specific application dependency. It establishes an outbound encrypted tailnet connection; no inbound router port forwarding is needed. The host-only Caddy origin at `127.0.0.1:8080` is the upstream. Tailscale Serve provides HTTPS with a tailnet certificate to authorized tailnet users.

Install Tailscale using the [official Linux installation instructions](https://tailscale.com/kb/1031/install-linux/) for the selected distribution, then authenticate locally on the store server. Do not put an auth key in this repository or paste it into chat.

```sh
sudo tailscale up
sudo tailscale status
```

After Caddy is healthy, enable HTTPS Serve on the store server:

```sh
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
sudo tailscale serve status
```

The owner/support user opens the store server's MagicDNS name shown by `tailscale status` (for example, `https://store-server.<tailnet>.ts.net`). Tailscale terminates HTTPS and forwards locally to Caddy on loopback. The Caddy origin is not exposed to the LAN. If your installed Tailscale CLI uses a different Serve syntax, consult its current `tailscale serve --help` output before enabling it.

Security requirements:

- Require MFA on the identity provider and approve every device joining the tailnet.
- Use Tailscale ACLs/grants to permit only named owner/support identities to reach the store server's TCP 443 service.
- Do not advertise the whole store LAN as a subnet route for this use case.
- Do not enable Tailscale Funnel; it would make the service publicly reachable.
- Keep the LAN firewall policy in place. Tailscale is an additional private management path, not a replacement for local network segmentation.
- Review tailnet membership and access logs monthly and remove lost/retired devices immediately.

Disable remote access:

```sh
sudo tailscale serve reset
sudo tailscale down
```

The LAN HTTPS endpoint remains available after remote access is disabled.

## Troubleshooting

- LAN browser certificate warning: verify the trusted Caddy root CA and hostname; do not bypass certificate validation on production POS devices.
- Remote owner cannot connect: check `tailscale status`, `tailscale serve status`, device approval, ACL/grant policy, and `curl -I http://127.0.0.1:8080/api/v1/health` on the host.
- Never solve remote-access issues by forwarding TCP 443 or 1433 on the store router.
