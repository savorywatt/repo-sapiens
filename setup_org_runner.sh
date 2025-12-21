#!/bin/bash
# Setup organization-level Gitea Actions runner

set -e

# Configuration
GITEA_URL="http://100.89.157.127:3000"
ORG_NAME="Foxshirestudios"
RUNNER_NAME="org-runner-1"

echo "🏃 Gitea Actions Organization Runner Setup"
echo "=========================================="
echo "Organization: $ORG_NAME"
echo "Gitea URL: $GITEA_URL"
echo

# Check if runner already exists
if [ -d "$HOME/.cache/act_runner" ]; then
    echo "⚠️  Found existing runner data at ~/.cache/act_runner"
    echo "   This script will set up an additional organization-level runner"
    echo
fi

# Download act_runner if not exists
if ! command -v act_runner &> /dev/null; then
    echo "📥 Downloading act_runner..."

    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        ARCH="arm64"
    fi

    # Download latest release
    RUNNER_VERSION="0.2.11"  # Update this to latest version
    DOWNLOAD_URL="https://dl.gitea.com/act_runner/${RUNNER_VERSION}/act_runner-${RUNNER_VERSION}-linux-${ARCH}"

    curl -L "$DOWNLOAD_URL" -o /tmp/act_runner
    chmod +x /tmp/act_runner
    sudo mv /tmp/act_runner /usr/local/bin/act_runner

    echo "✅ act_runner installed to /usr/local/bin/act_runner"
else
    echo "✅ act_runner already installed"
fi

echo
echo "📋 Next Steps:"
echo
echo "1. Generate a runner token from Gitea:"
echo "   Visit: $GITEA_URL/org/$ORG_NAME/settings/actions/runners"
echo "   Click 'Create new runner'"
echo "   Copy the registration token"
echo
echo "2. Register the runner (run these commands):"
echo
echo "   # Create config directory for org runner"
echo "   mkdir -p ~/.config/act_runner_org"
echo
echo "   # Register the runner (paste your token when prompted)"
echo "   act_runner register \\"
echo "     --instance $GITEA_URL \\"
echo "     --name $RUNNER_NAME \\"
echo "     --labels ubuntu-latest:docker://node:20-bullseye,ubuntu-22.04:docker://node:20-bullseye \\"
echo "     --config ~/.config/act_runner_org/config.yaml"
echo
echo "3. Run the runner as a service:"
echo
echo "   # Option A: Run in foreground (for testing)"
echo "   act_runner daemon --config ~/.config/act_runner_org/config.yaml"
echo
echo "   # Option B: Run as systemd service (recommended)"
echo "   sudo tee /etc/systemd/system/act_runner_org.service > /dev/null <<EOF"
echo "[Unit]"
echo "Description=Gitea Actions Runner (Organization: $ORG_NAME)"
echo "After=network.target"
echo ""
echo "[Service]"
echo "Type=simple"
echo "User=$USER"
echo "WorkingDirectory=$HOME"
echo "ExecStart=/usr/local/bin/act_runner daemon --config $HOME/.config/act_runner_org/config.yaml"
echo "Restart=always"
echo "RestartSec=10"
echo ""
echo "[Install]"
echo "WantedBy=multi-user.target"
echo "EOF"
echo
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable act_runner_org"
echo "   sudo systemctl start act_runner_org"
echo "   sudo systemctl status act_runner_org"
echo
echo "=========================================="
echo "🎯 Why Organization-Level Runner?"
echo "=========================================="
echo
echo "Benefits:"
echo "  ✅ Shared across ALL repos in the organization"
echo "  ✅ No need to set up runner for each repo"
echo "  ✅ Centralized management"
echo "  ✅ Better resource utilization"
echo
echo "All repos in $ORG_NAME will automatically use this runner!"
echo

# Create helper script for registration
cat > /tmp/register_org_runner.sh <<'REGSCRIPT'
#!/bin/bash
read -p "Enter the registration token from Gitea: " TOKEN

act_runner register \
  --instance http://100.89.157.127:3000 \
  --token "$TOKEN" \
  --name org-runner-1 \
  --labels ubuntu-latest:docker://node:20-bullseye,ubuntu-22.04:docker://node:20-bullseye \
  --config ~/.config/act_runner_org/config.yaml

if [ $? -eq 0 ]; then
    echo
    echo "✅ Runner registered successfully!"
    echo
    echo "Start the runner with:"
    echo "  act_runner daemon --config ~/.config/act_runner_org/config.yaml"
else
    echo
    echo "❌ Registration failed. Please check your token and try again."
fi
REGSCRIPT

chmod +x /tmp/register_org_runner.sh

echo "💡 Quick registration helper created at: /tmp/register_org_runner.sh"
echo "   Run it to easily register your runner with the token from Gitea"
echo
