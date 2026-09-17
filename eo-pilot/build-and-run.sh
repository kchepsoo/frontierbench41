#!/usr/bin/env bash
set -eo pipefail
test "$(id -u)" -ne 0
id | tee /work/logs/database-user.txt
date -u +%FT%TZ > /work/logs/started.txt
cd /work
commit=8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4
curl --fail --location --retry 3 --output cloudberry.tar.gz \
  "https://codeload.github.com/apache/cloudberry/tar.gz/$commit"
echo 'c799592ba523e6b341df9b6ad8a9abc8818eed6a92a6e91a242a02eabe84dc78  cloudberry.tar.gz' | sha256sum -c -
tar -xzf cloudberry.tar.gz --strip-components=1 -C /work/source
printf '%s\n' "$commit" > /work/logs/source-commit.txt
sha256sum cloudberry.tar.gz > /work/logs/source-sha256.txt

cp /protocol.md /work/logs/EO_PILOT_PROTOCOL.md
sha256sum /protocol.md > /work/logs/protocol-sha256.txt
cd /work/source
patch -p1 < /kit/pilot.patch
cp /kit/CCostModel*Legacy.cpp src/backend/gporca/libgpdbcost/src/
cp /kit/CCostModel*Legacy.h src/backend/gporca/libgpdbcost/include/gpdbcost/
cp /kit/pilot.patch /work/logs/applied.patch
python3 -m pip install --disable-pip-version-check --target /work/python duckdb==1.4.3 psycopg2-binary==2.9.10 2>&1 | tee /work/logs/pip.log

# Ephemeral loopback SSH is required by native cluster-management commands.
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -q -t ed25519 -N '' -f "$HOME/.ssh/native_gate"
cat "$HOME/.ssh/native_gate.pub" >> "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
ssh-keyscan -H cdw localhost 127.0.0.1 > "$HOME/.ssh/known_hosts"
cat > "$HOME/.ssh/config" <<'EOF'
Host cdw localhost 127.0.0.1
  IdentityFile ~/.ssh/native_gate
  IdentitiesOnly yes
  BatchMode yes
  StrictHostKeyChecking yes
EOF
chmod 600 "$HOME/.ssh/config"
ssh cdw id > /work/logs/loopback-ssh.txt

mkdir -p /work/install/lib
cp -a /usr/local/xerces-c/lib/libxerces-c*.so* /work/install/lib/
export LD_LIBRARY_PATH="/work/install/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cd /work/source
./configure --prefix=/work/install --enable-orca --disable-external-fts \
  --with-python --with-pythonsrc-ext --with-libxml --with-openssl \
  --with-includes=/usr/local/xerces-c/include \
  --with-libraries=/work/install/lib \
  2>&1 | tee /work/logs/configure.log
cp config.log /work/logs/config.log
jobs=$(nproc)
if [ "$jobs" -gt 4 ]; then jobs=4; fi
if [ -f /work/install/.native-build-complete ]; then
  echo 'Exact-source build cache restored; no data or timing results cached.' > /work/logs/build-cache.txt
else
  { time -p make -j"$jobs"; } 2>&1 | tee /work/logs/build.log
  { time -p make install; } 2>&1 | tee /work/logs/install.log
  touch /work/install/.native-build-complete
fi
sha256sum /work/install/bin/postgres > /work/logs/postgres-sha256.txt
mkdir -p /work/logs/audit
cat >> /work/install/greenplum_path.sh <<'AUDIT_ENV'
export GPORCA_AUDIT_P_FIXED=1
export GPORCA_AUDIT_DIR=/work/logs/audit
AUDIT_ENV
source /work/install/greenplum_path.sh
export PYTHONPATH="/work/python${PYTHONPATH:+:$PYTHONPATH}"
postgres --version > /work/logs/server-version.txt
pg_config --configure > /work/logs/server-configure.txt

# Coordinator-only optimizer controls must register before initdb can boot.
postgres --describe-config > /work/logs/guc-preflight.tsv
cd /work/source/gpAux/gpdemo
finish() {
  status=$?
  set +e
  gpstop -a -M immediate > /work/logs/shutdown.log 2>&1
  python3 - <<'COLLECT_LOGS'
from pathlib import Path
import shutil
root=Path('/work/source/gpAux/gpdemo/datadirs')
for p in root.rglob('*'):
    if p.is_file() and (p.suffix in ('.log', '.csv') or p.name.startswith('startup')):
        out=Path('/work/logs/cluster-details')/p.relative_to(root)
        out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,out)
COLLECT_LOGS
  exit "$status"
}
trap finish EXIT
export NUM_PRIMARY_MIRROR_PAIRS=2 WITH_MIRRORS=false WITH_STANDBY=false
export PORT_BASE=7000
make cluster 2>&1 | tee /work/logs/cluster.log
source gpdemo-env.sh
export PGHOST=localhost PGUSER=gpadmin PGDATABASE=postgres
psql -X -v ON_ERROR_STOP=1 -c 'SELECT version(); SHOW optimizer; SELECT gp_opt_version(); SELECT content,role,status,hostname FROM gp_segment_configuration ORDER BY dbid;' > /work/logs/native-state.txt
python3 -u /kit/run-pilot.py
ps -eo uid,pid,comm,args | awk '$3 == "postgres"' > /work/logs/server-processes.txt
test -s /work/logs/server-processes.txt
awk '$1 == 0 {bad=1} END {exit bad}' /work/logs/server-processes.txt
date -u +%FT%TZ > /work/logs/completed.txt
