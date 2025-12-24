#!/bin/bash
set -e
env_name="hits_omics"

# Set micromamba root prefix
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
MICROMAMBA_BIN="$MAMBA_ROOT_PREFIX/micromamba"

# Install micromamba if not available
if [ ! -f "$MICROMAMBA_BIN" ]; then
    echo "Installing micromamba..."
    
    # Create directory
    mkdir -p "$MAMBA_ROOT_PREFIX"
    
    # Download and install micromamba
    if [[ "$(uname)" == "Darwin" ]]; then
        if [[ "$(uname -m)" == "arm64" ]]; then
            ARCH="osx-arm64"
        else
            ARCH="osx-64"
        fi
    else
        ARCH="linux-64"
    fi
    
    curl -Ls https://micro.mamba.pm/api/micromamba/${ARCH}/latest | tar -xvj -C "$MAMBA_ROOT_PREFIX" --strip-components=1 bin/micromamba
    
    echo "micromamba installed at $MICROMAMBA_BIN"
fi

# Verify micromamba exists
if [ ! -f "$MICROMAMBA_BIN" ]; then
    echo "Error: micromamba not found at $MICROMAMBA_BIN"
    exit 1
fi

echo "Using micromamba at: $MICROMAMBA_BIN"

# Create environment
echo "Creating environment: $env_name"
"$MICROMAMBA_BIN" create -n $env_name -f environment.yml -y || "$MICROMAMBA_BIN" env update -n $env_name -f environment.yml -y

# Install additional packages
# echo "Installing additional packages from bio_env.yml..."
# "$MICROMAMBA_BIN" install -n $env_name -f bio_env.yml -y || true

# Install R packages if needed
if [ -f r_packages.yml ]; then
    echo "Installing R packages from r_packages.yml..."
    "$MICROMAMBA_BIN" env update -n $env_name --file r_packages.yml -y || true
fi

# Install R packages that couldn't be installed via conda due to dependency conflicts
# if [ -f install_r_packages.R ]; then
#     echo "Installing additional R packages via R's package manager..."
#     "$MICROMAMBA_BIN" run -n $env_name Rscript install_r_packages.R || echo "Warning: Some R packages may have failed to install. You can install them manually later."
# fi

# Install the main package in editable mode
echo "Installing biomni package..."
"$MICROMAMBA_BIN" run -n $env_name pip install -e ../../

echo "Installation complete!"
echo ""
echo "To activate the environment in a new shell, run:"
echo "  export MAMBA_ROOT_PREFIX=$MAMBA_ROOT_PREFIX"
echo "  eval \"\$($MICROMAMBA_BIN shell hook --shell bash)\"  # or --shell zsh for zsh"
echo "  micromamba activate $env_name"
echo ""
echo "Or use 'micromamba run' without activation:"
echo "  $MICROMAMBA_BIN run -n $env_name <command>"
