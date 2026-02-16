# Contributing

Thank you for your interest in contributing to the Real-Time Margin Risk Monitor!

## Educational Purpose

This project is designed for graduate-level computer science education. Contributions should maintain clarity and pedagogical value.

## Types of Contributions

We welcome:

1. **Bug Fixes**: Corrections to code, documentation, or configuration
2. **Documentation Improvements**: Clarifications, examples, diagrams
3. **New Exercises**: Additional learning exercises (see docs/08-exercises.md)
4. **Test Cases**: Unit tests, integration tests, scenario tests
5. **Performance Optimizations**: Improvements that maintain clarity
6. **Additional Features**: New risk methodologies, monitoring tools, etc.

## Guidelines

### Code Style

- **Python**: Follow PEP 8
- **Comments**: Explain "why", not "what"
- **Documentation**: Update relevant docs when changing functionality
- **Tests**: Add tests for new features

### Documentation Style

- **Clarity**: Write for graduate CS students, not finance experts
- **Examples**: Include concrete examples with numbers
- **Diagrams**: Use Mermaid for architecture diagrams
- **Math**: Show formulas with clear notation

### Commit Messages

Use conventional commits:

```
feat: Add volatility-based margin adjustment
fix: Correct beta-weighted calculation
docs: Clarify TIMS scenario grid
test: Add unit tests for enforcement logic
```

## Development Workflow

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-feature`
3. **Make** your changes
4. **Test** locally: `docker-compose up -d && python scripts/demo_scenario.py`
5. **Commit** with clear messages
6. **Push** to your fork
7. **Submit** a pull request

## Pull Request Process

1. **Description**: Clearly describe what and why
2. **Testing**: Show that it works (screenshots, logs)
3. **Documentation**: Update relevant docs
4. **Review**: Address feedback promptly

## Testing

### Local Testing

```bash
# Start services
docker-compose up -d

# Run demo
python scripts/demo_scenario.py

# Observe results
python scripts/observe_streams.py

# Check Spark UI
open http://localhost:8080
```

### Unit Tests

```bash
# Run Python tests
pytest tests/

# Run Spark tests
spark-submit --master local[2] tests/test_margin_calculator.py
```

## Code of Conduct

- Be respectful and constructive
- Focus on education and learning
- Help others understand concepts
- Acknowledge contributions

## Questions?

- Open an issue for questions
- Tag with `question` label
- Provide context and what you've tried

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Acknowledgments

Contributors will be acknowledged in the README and release notes.

Thank you for helping make this educational resource better!
