#!/usr/bin/env bash
# One-time (and repeatable) setup of the Lightsail server. Run as root over SSH:
#
#   DEPLOY_PUBLIC_KEY="ssh-ed25519 AAAA... deploy" sudo -E bash bootstrap-server.sh
#
# The instance was created by hand, so user data (cloud-init) cannot be applied to it; this
# script does the same job and stays in the repository so the server is reproducible.
# Safe to run again. It installs Docker and the AWS CLI, creates the `deploy` user and the
# /opt/skills layout, turns on unattended security upgrades, and installs the nightly backup
# timer. Ubuntu LTS on x86_64 or arm64 is assumed.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo -E bash $0)" >&2
  exit 1
fi
: "${DEPLOY_PUBLIC_KEY:?Set DEPLOY_PUBLIC_KEY to the public SSH key the deploy workflow will use}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg unzip unattended-upgrades

# ---- Docker Engine and the Compose plugin (Docker's own apt repository) ----
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
systemctl enable --now docker
systemctl restart docker

# ---- AWS CLI v2 (for the backup scripts) ----
if ! command -v aws >/dev/null 2>&1; then
  case "$(uname -m)" in
    x86_64) aws_zip="awscli-exe-linux-x86_64.zip" ;;
    aarch64) aws_zip="awscli-exe-linux-aarch64.zip" ;;
    *) echo "Unsupported CPU: $(uname -m)" >&2; exit 1 ;;
  esac
  tmp="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/${aws_zip}" -o "${tmp}/awscli.zip"
  unzip -q "${tmp}/awscli.zip" -d "${tmp}"
  "${tmp}/aws/install" --update
  rm -rf "$tmp"
fi

# ---- deploy user: key-only SSH, may run docker ----
if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash --groups docker deploy
fi
usermod --append --groups docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
printf '%s\n' "$DEPLOY_PUBLIC_KEY" > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

# ---- SSH hardening: keys only, no root login (checked before it is applied) ----
cat > /etc/ssh/sshd_config.d/99-skills.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF
if sshd -t; then
  systemctl reload ssh || systemctl reload sshd
else
  rm -f /etc/ssh/sshd_config.d/99-skills.conf
  echo "sshd rejected the hardening file; it was removed." >&2
fi

# ---- application layout ----
install -d -m 750 -o deploy -g deploy /opt/skills
install -d -m 750 -o deploy -g deploy /opt/skills/data
install -d -m 700 /opt/skills/data/postgres # the postgres image takes ownership on first start
# The app user in the image (uid 10001) writes here; the deploy group may read, so backup.sh works.
install -d -m 750 -o 10001 -g deploy /opt/skills/data/reports

# ---- unattended security upgrades ----
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

# ---- nightly backup timer ----
cat > /etc/systemd/system/skills-backup.service <<'UNIT'
[Unit]
Description=Back up the Skills database to S3
After=docker.service

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/opt/skills
ExecStart=/opt/skills/backup.sh
UNIT
cat > /etc/systemd/system/skills-backup.timer <<'UNIT'
[Unit]
Description=Nightly Skills database backup

[Timer]
OnCalendar=*-*-* 02:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now skills-backup.timer

echo "Bootstrap finished. Next: run the deploy workflow, which copies the compose file and scripts to /opt/skills."
