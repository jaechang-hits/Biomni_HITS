#!/bin/bash

echo "🚀 Installing HyperImpute and dependencies..."

# OPTIONAL: Activate biomni_env if needed
if conda env list | grep -q "biomni_env"; then
    echo "🔄 Activating biomni_env..."
    conda activate biomni_env
else
    echo "⚠️ biomni_env not found. Please activate your environment manually if needed."
fi

# Install hyperimpute with pip
pip install hyperimpute

echo "✅ HyperImpute installation complete!"
