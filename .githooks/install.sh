#!/bin/bash
# Git hook installation script for ztemplate repository automation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

print_info "Installing git hooks for ztemplate repository..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository. Please run this script from a git repository root."
    exit 1
fi

# Install pre-commit hook
if [ -f ".githooks/pre-commit/git-pre-commit" ]; then
    print_info "Installing pre-commit hook..."
    mkdir -p ".git/hooks"
    cp ".githooks/pre-commit/git-pre-commit" ".git/hooks/pre-commit"
    chmod +x ".git/hooks/pre-commit"
    print_info "Pre-commit hook installed successfully!"
else
    print_error "Pre-commit hook script not found: .githooks/pre-commit/git-pre-commit"
    exit 1
fi

# Install post-commit hook
if [ -f ".githooks/post-commit/git-post-commit" ]; then
    print_info "Installing post-commit hook..."
    cp ".githooks/post-commit/git-post-commit" ".git/hooks/post-commit"
    chmod +x ".git/hooks/post-commit"
    print_info "Post-commit hook installed successfully!"
else
    print_warning "Post-commit hook script not found. You can add it later if needed."
fi

# Install pre-push hook
if [ -f ".githooks/pre-push/git-pre-push" ]; then
    print_info "Installing pre-push hook..."
    cp ".githooks/pre-push/git-pre-push" ".git/hooks/pre-push"
    chmod +x ".git/hooks/pre-push"
    print_info "Pre-push hook installed successfully!"
else
    print_warning "Pre-push hook script not found. You can add it later if needed."
fi

print_info "Git hooks installation complete!"
print_info ""
print_info "The following hooks have been installed:"
print_info "  - pre-commit: Runs validation before committing"
print_info "  - post-commit: Runs after committing (if configured)"
print_info "  - pre-push: Runs before pushing (if configured)"
print_info ""
print_info "You can find the hook scripts in .githooks/ directory for future reference."

exit 0