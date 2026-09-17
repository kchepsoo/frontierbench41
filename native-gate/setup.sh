#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" -eq 0
test -d /kit
test -d /work/logs
if ! id gpadmin >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash gpadmin
fi
# Administrative setup occurs in the disposable container only. No host ports
# or Docker socket are exposed to it. The server's root guard is untouched.
install -d -o gpadmin -g gpadmin /work/source /work/install
chown gpadmin:gpadmin /work /work/logs
ssh-keygen -A
mkdir -p /run/sshd
/usr/sbin/sshd
exec su - gpadmin -c 'bash /kit/build-and-run.sh'
