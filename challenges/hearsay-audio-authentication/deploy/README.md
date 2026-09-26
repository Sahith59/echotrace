# Deploying ECHOTRACE (version 1)

One VM runs two containers:

- `app`: FastAPI + uvicorn, a single worker. It serves the landing page at `/`, the workspace at `/app/` and the API at `/api/`. Data lives in the `echotrace-data` volume, mounted at `/data`.
- `caddy`: HTTPS termination with automatic Let's Encrypt certificates on ports 80 and 443. It reverse-proxies to `app:8000`. The app port is never published.

Files in this directory: `docker-compose.yml`, `Caddyfile`, `entrypoint.sh`, `.env.example`, `vercel-build.sh`, `remote-update.sh`. The `Dockerfile` and `vercel.json` are one level up.

## Recommended layout: Vercel for the pages, the VM for the API

| Part | Where | Updates |
|---|---|---|
| Landing `/` and workspace `/app/` | Vercel Hobby (free), at `https://<domain>` | Automatic on every push |
| API and models `/api/*` | This VM, at `https://api.<domain>` | Automatic on every push to `master` through `.github/workflows/deploy-api.yml`, after the one-time setup below |

The browser only ever talks to `https://<domain>`. Vercel forwards `/api/*` to `https://api.<domain>`, so the session cookie, Origin checks and Google redirect all use the one public origin.

**Vercel project (once):**

1. vercel.com → **Add New → Project** → import `Sahith59/echotrace`.
2. **Root Directory**: `challenges/hearsay-audio-authentication`. Framework preset: **Other**. Leave build and output settings empty; `vercel.json` sets them.
3. **Environment variable**: `ECHOTRACE_API_ORIGIN=https://api.<domain>` (Production and Preview).
4. Deploy, then **Settings → Domains** → add `<domain>` and create the DNS record Vercel shows.
5. **Settings → Git → Production Branch**: the branch the live site follows (usually `master`).

**VM `.env` for this layout** (steps 7 onward): `ECHOTRACE_DOMAIN=api.<domain>`, `ECHOTRACE_PUBLIC_URL=https://<domain>`, `ECHOTRACE_ALLOWED_HOSTS=api.<domain>`. DNS: an A record for `api` pointing at the VM.

**Automatic API redeploys (once):** on the VM, create a deploy SSH key pair and authorise it (`ssh-keygen -t ed25519 -f ~/.ssh/gh_deploy -N ""` then `cat ~/.ssh/gh_deploy.pub >> ~/.ssh/authorized_keys`). In GitHub → repository **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | The VM's public IP |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_KEY` | Contents of `~/.ssh/gh_deploy` (the private key) |
| `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan -t ed25519 <VM IP>` run from your laptop |

Without `DEPLOY_HOST` the workflow skips itself. With it, every push to `master` that touches the backend, `Dockerfile` or `deploy/` runs `remote-update.sh` on the VM: fast-forward `~/echotrace`, rebuild, and wait for the health check. **Actions → Deploy API → Run workflow** redeploys by hand.

Limits of the Vercel hop: a proxied request must answer within 120 seconds. Uploads return as soon as the file is stored and analysis continues in the background, so this only affects very slow upload connections. Check a large upload once after launch.

The single-VM layout below (the VM serves everything at `https://<domain>`) still works; leave `ECHOTRACE_ALLOWED_HOSTS` empty for it.

## Read before deploying

- **Uploaded audio is stored on the server.** Original recordings, job results and the SQLite database live in the `echotrace-data` volume under `/data/workspace`. Whoever administers the VM can read them. Back up and delete them according to your own data policy.
- **One recording at a time.** Inference runs on CPU in one uvicorn worker. Jobs use an in-process queue and SQLite, so do not add workers or replicas. Other uploads wait in the queue.
- **Slow first request.** The pinned NII checkpoint (about 380 MB) downloads on first boot, before uvicorn starts. After every restart, the first analysis also loads the model into memory, so it takes noticeably longer.
- **The PyTorch wheels are large on both architectures.** `backend/uv.lock` pins `torch==2.14.0` from PyPI. For Linux it declares CUDA dependencies (`nvidia-*-cu13`, `cuda-bindings`) under the marker `sys_platform == 'linux'`, and the lock contains both `aarch64` and `x86_64` wheels for them. As locked, ARM64 (Ampere) and x86_64 builds **both** install CUDA-enabled PyTorch and its NVIDIA libraries. That adds several GB to the image, and a VM without a GPU never uses them; inference still runs on CPU. Getting CPU-only wheels means changing `pyproject.toml` and regenerating the lock (for example with a `pytorch-cpu` uv index). That change is not part of this deployment. Budget at least 15 GB of free disk for the build.
- The optional models (WavLM speaker comparison and faster-whisper transcription) are off by default. Turn them on with `ECHOTRACE_INSTALL_SPEAKER=1` and `ECHOTRACE_INSTALL_WHISPER=1`. Each one downloads once into the volume.

## 1. Get a domain

Pick one:

| Option | Cost | Notes |
|---|---|---|
| GitHub Student Developer Pack, `.tech` via get.tech | Free for 1 year | Claim through education.github.com/pack. |
| Namecheap `.me` through the Student Pack | Free for 1 year | Manage DNS in Namecheap's "Advanced DNS" tab. |
| DuckDNS (`<name>.duckdns.org`) | Free | No-cost fallback. Sign in at duckdns.org, create a subdomain and set its IP. |

You create the DNS record in step 4, after the VM has a public IP.

## 2. Create the Oracle Cloud Always Free VM

1. Sign up at cloud.oracle.com and choose a home region that has Ampere A1 capacity. Always Free resources exist only in the home region.
2. Go to **Compute → Instances → Create instance**.
   - Image: **Canonical Ubuntu 24.04** (22.04 also works).
   - Shape: **VM.Standard.A1.Flex**, **2 OCPU, 12 GB memory** (the current Always Free allowance).
   - Networking: create or pick a VCN with a public subnet and **assign a public IPv4 address**.
   - SSH keys: upload your public key.
   - Boot volume: the default size is enough for the OS.
   If you get "Out of capacity", retry later or pick another availability domain.
3. Create a block volume for Docker data: **Storage → Block Volumes → Create**, 100 GB. Always Free covers 200 GB of block storage in total, boot volumes included. Attach it to the instance using **Paravirtualized** attachment.
4. Reserve the public IP (optional but recommended): **Networking → Reserved public IPs**. Assign it to the instance's VNIC so the IP survives a stop/start.

## 3. Open ports 80 and 443

Both layers are required.

**VCN security list.** Open **Networking → Virtual cloud networks → your VCN → Security Lists → Default** and add ingress rules:

| Source CIDR | Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | 80 |
| `0.0.0.0/0` | TCP | 443 |
| `0.0.0.0/0` | UDP | 443 (optional, HTTP/3) |

**Instance firewall.** Oracle's Ubuntu images ship iptables rules that end in `REJECT`. SSH in (`ssh ubuntu@<public-ip>`) and insert the ACCEPT rules **above** the REJECT line:

```bash
sudo iptables -L INPUT --line-numbers -n        # note the line number of the REJECT rule, e.g. 5
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 5 -m state --state NEW -p udp --dport 443 -j ACCEPT
sudo apt-get update && sudo apt-get install -y netfilter-persistent iptables-persistent
sudo netfilter-persistent save
```

Do not run `ufw enable` on top of these rules, and do not flush the chain; that can cut off SSH.

## 4. Point DNS at the VM

Create an **A record**: host `@` (or a subdomain such as `echotrace`), value = the VM's public IPv4, TTL 300. For DuckDNS, enter the IP on the DuckDNS dashboard. Check it with:

```bash
dig +short <your-domain>        # must print the VM's public IP before Caddy can get a certificate
```

## 5. Mount the block volume and install Docker

1. Run the iSCSI attach commands. Paravirtualized attachments need none. For iSCSI, copy the commands from **Attached block volumes → ⋯ → iSCSI commands**. Then format and mount the volume at `/var/lib/docker`, so images and the named volumes live on it:

   ```bash
   lsblk                                              # find the new disk, e.g. /dev/sdb
   sudo mkfs.ext4 -L dockerdata /dev/sdb
   sudo mkdir -p /var/lib/docker
   echo 'LABEL=dockerdata /var/lib/docker ext4 defaults,_netdev,nofail 0 2' | sudo tee -a /etc/fstab
   sudo mount -a && df -h /var/lib/docker
   ```

2. Install Docker Engine and the Compose plugin from Docker's apt repository:

   ```bash
   sudo apt-get install -y ca-certificates curl git
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
     | sudo tee /etc/apt/sources.list.d/docker.list
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker "$USER"    # log out and back in afterwards
   docker compose version
   ```

## 6. Clone the repository

The repository is private. Pick one way to authenticate: add a read-only **deploy key** (an SSH key generated on the VM, added under the repository's *Settings → Deploy keys*), or use a fine-grained personal access token with read-only contents access.

```bash
git clone git@github.com:Sahith59/echotrace.git ~/echotrace
cd ~/echotrace/challenges/hearsay-audio-authentication/deploy
```

## 7. Configure `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Set at least:

- `ECHOTRACE_DOMAIN=<your-domain>` (bare hostname; `api.<domain>` in the Vercel layout)
- `ECHOTRACE_PUBLIC_URL=https://<your-domain>` (no trailing slash; the Vercel domain in the Vercel layout)
- `ECHOTRACE_ALLOWED_HOSTS=api.<domain>` (Vercel layout only)
- `ECHOTRACE_AUTH=required`, `ECHOTRACE_TRUST_PROXY=1` (already set)

Google sign-in (step 10) and Groq (`GROQ_API_KEY`) are optional. Leave `ECHOTRACE_MAX_RECORDINGS_PER_USER` commented out unless you set a number.

## 8. Build and start

```bash
docker compose up -d --build
```

The first build downloads Node, Python, FFmpeg and the locked Python dependencies, and it takes a while on 2 OCPU. On first boot, the entrypoint downloads and verifies the NII weights (about 380 MB) into `/data/artifacts` before it starts uvicorn.

## 9. Check that it is running

```bash
docker compose ps                         # app should become "healthy"; the health check allows 20 min for first boot
docker compose logs -f app                # watch the "[entrypoint]" lines, then uvicorn startup
docker compose logs -f caddy              # certificate issuance for your domain
curl -fsS https://<your-domain>/api/health
```

Open `https://<your-domain>/` (landing page) and `https://<your-domain>/app/` (workspace).

If the app exits immediately, read the `[entrypoint] ERROR:` line. A missing `ECHOTRACE_PUBLIC_URL` and a failed model download are both reported there. If Caddy cannot get a certificate, check the DNS record and ports 80/443 at both firewall layers.

## 10. Google OAuth (optional)

1. In Google Cloud Console, create or select a project.
2. Go to **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - App name, support email, developer contact.
   - Scopes: `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile`.
   - Publishing status: leave it in **Testing** for v1, and add every account that should sign in under **Test users**. Only test users can sign in while the app is in Testing mode.
3. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**.
   - Authorized JavaScript origins: `https://<your-domain>`
   - Authorized redirect URIs: `https://<your-domain>/api/auth/google/callback`
4. Copy the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
5. Apply the change: `docker compose up -d app` (this recreates the container so it picks up the new `.env`).

The redirect URI is built from `ECHOTRACE_PUBLIC_URL`, so the two must match exactly.

## 11. Update and redeploy

With the GitHub secrets from the Vercel layout section, pushes to `master` do this automatically. By hand:

```bash
cd ~/echotrace && git pull
cd challenges/hearsay-audio-authentication/deploy
docker compose up -d --build
docker image prune -f
```

Weights, the workspace and the database persist in `echotrace-data` across rebuilds. After the rebuild, the model loads again on the first analysis.

## 12. Back up the data volume

The volume is named `echotrace_echotrace-data`. Stop the app first, so the SQLite database is not copied mid-write:

```bash
cd ~/echotrace/challenges/hearsay-audio-authentication/deploy
docker compose stop app
docker run --rm -v echotrace_echotrace-data:/data:ro -v "$PWD":/backup busybox \
  tar czf /backup/echotrace-data-$(date +%F).tgz -C /data workspace
docker compose start app
```

This backs up `workspace` (recordings, results, database) and skips the re-downloadable model weights. Add `artifacts` to the tar arguments to keep those too. Copy the archive off the VM, for example with `scp`. It contains uploaded audio, so store it accordingly. To restore, stop the app and extract the archive into the volume with the same `docker run` pattern, without `:ro` and using `tar xzf`.

## Alternative: Azure for Students

1. With Azure for Students credit, create a **Linux VM**: Ubuntu 24.04, size **B2s** (2 vCPU, 4 GB RAM, x86_64), with a Standard public IP.
2. In the VM's **Network security group**, add inbound rules for TCP 80 and TCP 443. Azure Ubuntu images do not add the iptables REJECT rules, so step 3's instance-firewall part is not needed.
3. Optionally attach a data disk (Standard SSD) and mount it at `/var/lib/docker` as in step 5.
4. Follow steps 4 and 5.2 through 12 unchanged. The same `docker-compose.yml` works.

Notes for B2s: 4 GB RAM is tight for PyTorch and the NII model, so keep `ECHOTRACE_INSTALL_SPEAKER=0` and `ECHOTRACE_INSTALL_WHISPER=0`, and consider adding a swap file. The x86_64 build installs the CUDA-enabled PyTorch wheels from the lockfile, which are unused on this CPU-only VM. B2s bills against the credit while it runs, so stop the VM when you are not using it.
