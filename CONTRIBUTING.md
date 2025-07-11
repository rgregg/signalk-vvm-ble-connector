# Contributing to SignalK VVM BLE Connector

Thank you for your interest in contributing to the SignalK VVM BLE Connector project! This document provides guidelines and instructions for contributing to this repository.

## Branch Strategy

This project follows a two-branch workflow:

- **`dev`** - Development/beta branch where all new features and fixes are integrated
- **`main`** - Release branch containing stable, production-ready code

### Important Rules:
- 🚨 **All pull requests must target the `dev` branch**
- The `main` branch should only receive updates through merges from `dev`
- Never commit directly to either `main` or `dev` branches

## Getting Started

### Prerequisites

- Python 3.8+ (tested with 3.8, 3.9, 3.10)
- Git
- Access to a Linux system with Bluetooth capabilities (for full testing)

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/signalk-vvm-ble-connector.git
   cd signalk-vvm-ble-connector
   ```

2. **Create a feature branch from `dev`:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pylint  # For code linting
   ```

4. **Create logs directory for testing:**
   ```bash
   mkdir -p logs
   ```

5. **Run tests to verify setup:**
   ```bash
   PYTHONPATH=. python tests/test_blelogic.py
   ```

## Making Changes

### Code Quality Standards

All code contributions must meet these quality standards:

1. **Linting**: Code must pass PyLint checks
   ```bash
   pylint $(git ls-files '*.py')
   ```

2. **Testing**: 
   - Existing tests must continue to pass
   - New features should include appropriate tests
   - Run tests with: `PYTHONPATH=. python tests/test_blelogic.py`

3. **Code Style**:
   - Follow PEP 8 Python style guidelines
   - Use meaningful variable and function names
   - Include docstrings for public functions and classes
   - Keep functions focused and reasonably sized

### Making Your Changes

1. **Write clear, focused commits:**
   - Use descriptive commit messages
   - Make atomic commits (one logical change per commit)
   - Reference issues when applicable (e.g., "Fixes #123")

2. **Test thoroughly:**
   - Run existing tests to ensure no regressions
   - Test your changes manually if possible
   - Consider edge cases and error conditions

3. **Update documentation:**
   - Update README.md if your changes affect setup or usage
   - Add comments for complex logic
   - Update configuration examples if needed

## Pull Request Process

### Before Submitting

1. **Ensure your branch is up to date:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout your-feature-branch
   git rebase dev
   ```

2. **Run quality checks:**
   ```bash
   # Run linting
   pylint $(git ls-files '*.py')
   
   # Run tests
   PYTHONPATH=. python tests/test_blelogic.py
   ```

3. **Review your changes:**
   ```bash
   git diff dev..HEAD
   ```

### Submitting Your Pull Request

1. **Push your branch:**
   ```bash
   git push origin your-feature-branch
   ```

2. **Create a pull request:**
   - **Target the `dev` branch** (not main!)
   - Use a clear, descriptive title
   - Provide a detailed description of your changes
   - Reference any related issues
   - Include testing notes if applicable

3. **Pull request template:**
   ```markdown
   ## Description
   Brief description of what this PR does.
   
   ## Changes Made
   - List specific changes
   - Include any breaking changes
   
   ## Testing
   - [ ] Existing tests pass
   - [ ] New tests added (if applicable)
   - [ ] Manual testing performed
   
   ## Related Issues
   Fixes #123 (if applicable)
   ```

### Review Process

- Maintainers will review your pull request
- Address any feedback promptly
- Be responsive to questions and suggestions
- Once approved, maintainers will merge into `dev`

## Types of Contributions

### Bug Fixes
- Report bugs via GitHub Issues with detailed reproduction steps
- Include system information, error messages, and logs
- Search existing issues before creating new ones

### Feature Requests
- Discuss significant features in GitHub Issues first
- Provide clear use cases and justification
- Consider backward compatibility

### Documentation Improvements
- Typo fixes and clarifications are always welcome
- Help improve setup instructions
- Add examples and troubleshooting guides

### Code Contributions
- Bug fixes and performance improvements
- New device support or additional parameters
- Code refactoring and optimization

## Development Guidelines

### Docker Development
The project includes Docker support. To test Docker builds:

```bash
# Build the image
docker build -t vvm_monitor .

# Test with configuration
docker run -v ./config:/app/config vvm_monitor
```

### Configuration Testing
Test configuration changes with the example file:
```bash
cp vvm_monitor.example.yaml config/vvm_monitor.yaml
# Modify as needed for testing
```

### Bluetooth Testing
Full BLE testing requires:
- Linux system with BlueZ
- Physical Vessel View Mobile device
- Appropriate permissions for Bluetooth access

## Community Guidelines

### Be Respectful
- Use welcoming and inclusive language
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully

### Be Collaborative
- Help others learn and contribute
- Share knowledge and best practices
- Provide helpful feedback on pull requests

### Be Patient
- Maintainers are volunteers with limited time
- Complex features may take time to review
- Follow up politely if you don't hear back

## Getting Help

- **Questions**: Open a GitHub Discussion or Issue
- **Bugs**: Use GitHub Issues with detailed information
- **Security Issues**: Email maintainers privately (see README for contact)

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to SignalK VVM BLE Connector! 🚢⚓