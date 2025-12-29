#!/usr/bin/env Rscript

# Script to install R packages that couldn't be installed via conda due to dependency conflicts
# These packages are installed after the conda environment is created

# Set repository
options(repos = c(CRAN = "https://cran.rstudio.com/"))

# Function to install a package if it's not already installed
install_if_missing <- function(package_name, bioconductor = FALSE) {
  if (!require(package_name, character.only = TRUE, quietly = TRUE)) {
    cat(sprintf("Installing package: %s\n", package_name))

    if (bioconductor) {
      if (!require("BiocManager", quietly = TRUE)) {
        install.packages("BiocManager", dependencies = TRUE)
      }
      BiocManager::install(package_name, update = FALSE, ask = FALSE, dependencies = TRUE)
    } else {
      install.packages(package_name, dependencies = TRUE)
    }

    # Check if installation was successful
    if (require(package_name, character.only = TRUE, quietly = TRUE)) {
      cat(sprintf("✓ Successfully installed %s\n", package_name))
    } else {
      cat(sprintf("✗ Failed to install %s\n", package_name))
    }
  } else {
    cat(sprintf("✓ Package %s is already installed\n", package_name))
  }
}

cat("Installing R packages that couldn't be installed via conda...\n\n")

# Install BiocManager first (needed for Bioconductor packages)
cat("Checking BiocManager...\n")
if (!require("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager", dependencies = TRUE)
}

# Packages that couldn't be installed via conda due to dependency conflicts:
# - devtools: conflicts with r-testthat -> r-brio
# - timeROC: conflicts with r-pec dependency
# - survivalROC: doesn't exist in conda channels

cat("\nInstalling devtools...\n")
install_if_missing("devtools")

cat("\nInstalling timeROC...\n")
install_if_missing("timeROC")

cat("\nInstalling survivalROC...\n")
install_if_missing("survivalROC", bioconductor = TRUE)

cat("\n========================================\n")
cat("R package installation completed!\n")
cat("If you encounter issues, please install packages manually.\n")
