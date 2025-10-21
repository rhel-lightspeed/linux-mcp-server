#!/bin/bash
# Deploy Linux MCP Server to OpenShift

set -e

echo "🚀 Deploying Linux MCP Server to OpenShift"
echo ""

# Configuration
NAMESPACE="rhel-mcp"
SSH_KEY_PATH="$HOME/.ssh/id_rsa"

# Check if logged into OpenShift
if ! oc whoami &>/dev/null; then
  echo "❌ Not logged into OpenShift. Please run 'oc login' first."
  exit 1
fi

echo "✅ Logged in as: $(oc whoami)"
echo ""

# Create namespace if it doesn't exist
echo "📦 Creating namespace: $NAMESPACE"
oc create namespace $NAMESPACE --dry-run=client -o yaml | oc apply -f -

# Create SSH secret
echo "🔑 Creating SSH secret..."
if [ ! -f "$SSH_KEY_PATH" ]; then
  echo "❌ SSH key not found at: $SSH_KEY_PATH"
  echo "Please update SSH_KEY_PATH in this script or create the key"
  exit 1
fi

oc create secret generic linux-mcp-ssh-keys \
  --from-file=id_rsa=$SSH_KEY_PATH \
  --namespace=$NAMESPACE \
  --dry-run=client -o yaml | oc apply -f -

echo "✅ SSH secret created"
echo ""

# Apply manifests
echo "☸️  Applying Kubernetes manifests..."
oc apply -f openshift/serviceaccount.yaml
oc apply -f openshift/configmap.yaml
oc apply -f openshift/pvc.yaml
oc apply -f openshift/deployment.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml

echo ""
echo "⏳ Waiting for deployment to be ready..."
oc rollout status deployment/linux-mcp-server -n $NAMESPACE --timeout=5m

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Deployment Status:"
oc get pods -n $NAMESPACE
echo ""
echo "🌐 Route URL:"
oc get route linux-mcp-server -n $NAMESPACE -o jsonpath='{.spec.host}'
echo ""
echo ""
echo "📝 Useful commands:"
echo "  View logs:  oc logs -f deployment/linux-mcp-server -n $NAMESPACE"
echo "  Get pods:   oc get pods -n $NAMESPACE"
echo "  Describe:   oc describe deployment linux-mcp-server -n $NAMESPACE"
echo "  Shell:      oc exec -it deployment/linux-mcp-server -n $NAMESPACE -- /bin/bash"

