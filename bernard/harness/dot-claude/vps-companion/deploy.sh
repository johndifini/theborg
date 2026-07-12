#!/usr/bin/env bash
# deploy.sh — install the health-wiki companion onto the VPS. Run ON the VPS
# from inside the bundle directory:
#
#   PERSON_NAME="Jane" COMPANION_NAME="Wren" bash deploy.sh
#
# Idempotent: safe to re-run. Does NOT touch ~/.openclaw/openclaw.json — the
# agent/channel/binding additions are applied separately (see
# openclaw-config-patch.md) so a JSON5 config with comments is never sed-mangled.
set -euo pipefail

# systemctl --user needs these when run over non-interactive SSH
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

: "${PERSON_NAME:?Set PERSON_NAME=\"...\" (the one allowed user, as the agent should call them)}"
COMPANION_NAME="${COMPANION_NAME:-Wren}"
# What the agent calls the patient in conversation. Wiki pages are pseudonymized
# (PATIENT-001); set this to the name {{PERSON_NAME}} actually uses, or leave the
# safe default.
PATIENT_NAME="${PATIENT_NAME:-PATIENT-001}"

BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"
WS="$HOME/health-wiki-workspace"

echo "==> Backing up OpenClaw config"
[ -f "$HOME/.openclaw/openclaw.json" ] && \
  cp "$HOME/.openclaw/openclaw.json" "$HOME/.openclaw/openclaw.json.bak.$(date +%Y%m%d%H%M%S)"

echo "==> Creating directories"
mkdir -p "$WS/skills/publish-brief" "$WS/briefs" "$WS/infra" "$HOME/health-wiki-mirror"
chmod 700 "$WS" "$WS/briefs" "$HOME/health-wiki-mirror"

echo "==> Installing workspace files (substituting names)"
SUBST=(-e "s/{{PERSON_NAME}}/$PERSON_NAME/g" -e "s/{{COMPANION_NAME}}/$COMPANION_NAME/g" -e "s/{{PATIENT_NAME}}/$PATIENT_NAME/g")
for f in AGENTS.md IDENTITY.md SOUL.md TOOLS.md; do
  sed "${SUBST[@]}" "$BUNDLE_DIR/workspace/$f" > "$WS/$f"
done
for f in SKILL.md make_brief_pdf.py; do
  sed "${SUBST[@]}" "$BUNDLE_DIR/workspace/skills/publish-brief/$f" > "$WS/skills/publish-brief/$f"
done
chmod +x "$WS/skills/publish-brief/make_brief_pdf.py"
# Retired HTML-link pipeline — remove so the agent can't follow stale instructions
rm -f "$WS/skills/publish-brief/publish_brief.py" "$WS/skills/publish-brief/template.html" "$WS/infra/briefs_server.py"

echo "==> Fonts for PDF rendering (unicode-safe)"
FD="$WS/skills/publish-brief/fonts"; mkdir -p "$FD"
for f in DejaVuSans.ttf DejaVuSans-Bold.ttf DejaVuSans-Oblique.ttf; do
  [ -s "$FD/$f" ] || curl -fsSL -o "$FD/$f" "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/$f" \
    || echo "WARN: could not fetch $f — PDFs fall back to latin-1 transliteration"
done

if [ ! -f "$WS/wiki-question-inbox.md" ]; then
  printf '# Wiki Question Inbox\n\nOne line per gap: `- YYYY-MM-DD — question — what was missing`\n\n' \
    > "$WS/wiki-question-inbox.md"
fi

echo "==> Renderers (workspace venv — no sudo needed)"
[ -x "$WS/.venv/bin/python" ] || python3 -m venv "$WS/.venv"
"$WS/.venv/bin/pip" install -q --upgrade markdown fpdf2

echo "==> Cleanup timer (systemd user unit); retiring HTML briefs server if present"
mkdir -p "$HOME/.config/systemd/user"
systemctl --user disable --now briefs-server.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/briefs-server.service"
cp "$BUNDLE_DIR/infra/briefs-cleanup.service" \
   "$BUNDLE_DIR/infra/briefs-cleanup.timer" \
   "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now briefs-cleanup.timer
loginctl enable-linger "$USER" 2>/dev/null \
  || echo "WARN: could not enable linger — cleanup timer stops when you log out; run: sudo loginctl enable-linger $USER"

echo
echo "==> Done. Remaining manual steps:"
echo "  1. Briefs are WhatsApp PDF attachments — public hosting must stay OFF:"
echo "       tailscale serve reset && tailscale funnel status   # expect: no serve config"
echo "  2. Apply the OpenClaw config patch (first deploy only): see openclaw-config-patch.md"
echo "  3. Link the WhatsApp number (QR) and restart the gateway (first deploy only)"
echo "  4. Smoke test:"
echo "       printf '# Test\n\nHello **world**\n' > /tmp/t.md"
echo "       $WS/.venv/bin/python $WS/skills/publish-brief/make_brief_pdf.py /tmp/t.md --title 'Test brief'"
