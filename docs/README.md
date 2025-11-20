# Documentation Index

Welcome to the Language Learning Flashcard App documentation. This documentation reflects the current state of the application and provides comprehensive information about its features, architecture, and development practices.

## 📚 Documentation Overview

### [Architecture & Configuration](./architecture.md)
Complete overview of the application's architecture, configuration system, and design decisions.

**Topics covered:**
- Flask blueprint-based architecture
- Unified configuration management (local, production, testing)
- Dual-store system (Google Sheets + SQLite)
- Session management and security features
- Development workflow and deployment

### [Listening Mode](./listening-mode.md)
Comprehensive guide to the listening mode feature - sequential audio playback with mobile optimization.

**Topics covered:**
- Chrome iOS autoplay solution ("Touch Strategy")
- Smart caching system for performance
- Mobile audio unlock strategies
- Infinite loop playback with card reshuffling
- Session management and error handling

### [TTS (Text-to-Speech) System](./tts-system.md)
Complete documentation of the Portuguese TTS system with Google Cloud integration.

**Topics covered:**
- Google Cloud TTS API integration
- Audio caching with Google Cloud Storage
- Mobile audio optimization
- Error handling and performance optimization
- Security and monitoring considerations

### [Development Guide](./development-guide.md)
Practical guide for developers working on the application.

**Topics covered:**
- Setup and configuration
- Development workflow and code quality rules
- Testing and debugging procedures
- API development guidelines
- Deployment and troubleshooting

## 🚀 Quick Start

### For New Developers
1. Start with [Development Guide](./development-guide.md) for setup instructions
2. Read [Architecture & Configuration](./architecture.md) to understand the system
3. Explore specific feature documentation as needed

### For Feature Understanding
- **Audio Features:** [TTS System](./tts-system.md) + [Listening Mode](./listening-mode.md)
- **User Management:** [User Properties System](./user-properties.md)
- **System Architecture:** [Architecture & Configuration](./architecture.md)

### For Maintenance
- **Development:** [Development Guide](./development-guide.md)
- **Deployment:** [Architecture & Configuration](./architecture.md#deployment)
- **Troubleshooting:** [Development Guide](./development-guide.md#troubleshooting)

## 📋 Current Feature Status

### ✅ Fully Implemented
- **Configuration System** - Unified config with environment detection
- **User Properties** - Language settings with database storage
- **Listening Mode** - Mobile-optimized audio playback
- **TTS System** - Google Cloud TTS with caching
- **Authentication** - Google OAuth integration
- **Database Management** - SQLAlchemy models with migrations
- **Blueprint Architecture** - Modular route organization
- **Session Management** - Centralized session handling
- **PWA Support** - Progressive web app capabilities

### 🔧 Production Ready
All major features are production-ready and deployed on Railway with:
- Automatic environment detection
- Secure credential management
- Comprehensive error handling
- Mobile optimization
- Performance caching

## 🏗️ Architecture Overview

```
Frontend (JavaScript + Bootstrap)
├── TTSManager (Audio playback)
├── ListeningManager (Sequential playback)
└── UI Components (Settings, Cards, etc.)

Backend (Flask + Blueprint Architecture)
├── Routes (auth, flashcard, api, settings, admin)
├── Services (TTS, Google Sheets, User Management)
├── Models (Pydantic + SQLAlchemy)
└── Configuration (Environment-aware)

External Services
├── Google Cloud TTS (Audio generation)
├── Google Sheets API (Content management)
├── Google OAuth (Authentication)
└── Google Cloud Storage (Audio caching)
```

## 📝 Documentation Maintenance

### Last Updated
This documentation was last updated to reflect the current state of the application as of January 2025.

### Updating Documentation
When making changes to the application:
1. Update the relevant documentation files
2. Keep examples and code snippets current
3. Update feature status if needed
4. Review for accuracy and completeness

### Documentation Standards
- **Current State Focus:** Document what exists, not what's planned
- **Code Examples:** Include working code examples
- **Rationale:** Explain design decisions and trade-offs
- **Completeness:** Cover both happy path and error scenarios

## 🔗 Additional Resources

### Code Quality
- Pre-commit hooks with ruff linting
- Type hints required for all functions
- Comprehensive error handling
- Security scanning with bandit

### External Documentation
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Google Cloud TTS](https://cloud.google.com/text-to-speech)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Railway Deployment](https://railway.app/docs)

### Development Tools
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- [Pydantic](https://pydantic.dev/) - Data validation
- [SQLAlchemy](https://sqlalchemy.org/) - Database ORM
- [Bootstrap](https://getbootstrap.com/) - Frontend framework

---

*This documentation reflects the current state of the Language Learning Flashcard App. For the most up-to-date information, refer to the source code and commit history.*
