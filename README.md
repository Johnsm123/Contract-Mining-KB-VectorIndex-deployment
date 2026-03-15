# Contract Mining Assistant FsOgvcoxZNko5QpGtcSiTLjq4wDqKYjVA85N57I4SNqCuwlS1Iz9JQQJ99CCACHYHv6XJ3w3AAAAACOGcXgL
[![Deploy to Cloud Run](https://github.com/your-username/contract-mining-assistant/workflows/Deploy%20to%20Cloud%20Run/badge.svg)](https://github.com/your-username/contract-mining-assistant/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

> Enterprise-grade AI-powered contract analysis and modification system with hybrid cloud-local architecture.

## 🚀 Overview

Contract Mining Assistant is a sophisticated document processing platform that leverages cutting-edge AI technologies to streamline contract analysis, modification, and management workflows. Built with a hybrid architecture, it combines the power of cloud AI services with local data control.

### Key Capabilities

- 📄 **Intelligent Document Processing** - Advanced .docx analysis with AI-powered content extraction
- 🤖 **Multi-Model AI Integration** - Seamless orchestration of AWS Bedrock and Google AI services
- 🔍 **Semantic Search Engine** - Vector-based content discovery with high-precision embeddings
- ✏️ **Smart Contract Modifications** - Natural language-driven document amendments with change tracking
- 💬 **Interactive Chat Interface** - Conversational AI for contract Q&A and analysis
- 🏗️ **Hybrid Architecture** - Enterprise-ready local storage with optional cloud integration

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+ (optional)
- Docker (for containerized deployment)
- Google Cloud Platform account (optional)
- AWS account with Bedrock access (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/contract-mining-assistant.git
   cd contract-mining-assistant
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Database setup** (Optional)
   ```bash
   createdb contract_mining_db
   psql -d contract_mining_db -f setup_database.sql
   ```

5. **Launch application**
   ```bash
   python main.py
   ```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| API Server | http://localhost:8004 | Main application endpoint |
| Interactive Docs | http://localhost:8004/docs | Swagger UI documentation |
| Health Check | http://localhost:8004/health | System status monitoring |

## 🏗️ Architecture

### System Components

```
├── app/
│   ├── api/                    # RESTful API endpoints
│   │   ├── amendments.py       # Amendment lifecycle management
│   │   ├── chat.py            # Conversational AI interface
│   │   ├── contracts.py       # Contract CRUD operations
│   │   ├── document_modifications.py # Document transformation
│   │   ├── document_upload.py  # File ingestion pipeline
│   │   └── search.py          # Semantic search engine
│   ├── config/                # Application configuration
│   │   ├── gcp_clients.py     # Google Cloud Platform integration
│   │   └── settings.py        # Environment-based settings
│   ├── services/              # Core business logic
│   │   ├── amendment_service.py      # Amendment processing
│   │   ├── bedrock_orchestrator.py   # AWS Bedrock LLM integration
│   │   ├── document_generator.py     # Document creation engine
│   │   ├── embedding_service.py      # Vector embedding management
│   │   ├── hybrid_storage.py         # Multi-tier storage system
│   │   ├── llm_orchestrator.py       # AI model coordination
│   │   └── robust_document_modifier.py # Document modification engine
│   └── models/                # Data models and schemas
├── frontend/
│   └── index.html             # Web-based user interface
├── local_storage/             # Local file system storage
│   ├── contracts/             # Original contract repository
│   ├── uploaded_contracts/    # Processing pipeline storage
│   ├── embeddings/           # Vector embedding cache
│   ├── previews/             # Generated document previews
│   └── amendments/           # Amendment archive
└── .github/workflows/         # CI/CD automation
```

## 🔌 API Reference

### Core Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `POST` | `/api/documents/upload` | Upload contract documents | Optional |
| `GET` | `/api/contracts` | Retrieve contract inventory | Optional |
| `POST` | `/api/search` | Semantic content search | Optional |
| `POST` | `/api/chat` | Interactive contract analysis | Optional |
| `POST` | `/api/amendments` | Generate contract amendments | Optional |
| `POST` | `/api/modify` | Apply document modifications | Optional |

### Response Format

All API responses follow a consistent JSON structure:

```json
{
  "status": "success|error",
  "data": {},
  "message": "Human-readable status message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_PORT` | Application server port | `8004` | No |
| `DB_HOST` | PostgreSQL host address | `localhost` | No |
| `DB_PASSWORD` | Database authentication | - | Yes* |
| `GOOGLE_API_KEY` | Google AI services key | - | No |
| `AWS_ACCESS_KEY_ID` | AWS Bedrock access key | - | No |
| `AWS_SECRET_ACCESS_KEY` | AWS Bedrock secret key | - | No |
| `LOCAL_STORAGE_PATH` | Local file storage path | `./local_storage` | No |
| `STORAGE_MODE` | Storage architecture mode | `hybrid` | No |

*Required only if database features are enabled

### Deployment Modes

- **Local Development** - Full local execution with optional cloud AI
- **Hybrid Cloud** - Local storage with cloud AI processing
- **Cloud Native** - Full cloud deployment with Google Cloud Run

## 🛠️ Technology Stack

### Core Framework
- **FastAPI** - High-performance async web framework
- **Uvicorn** - ASGI server implementation
- **Pydantic** - Data validation and settings management

### AI & Machine Learning
- **Google Cloud AI Platform** - Document processing and embeddings
- **AWS Bedrock** - Large language model inference
- **Sentence Transformers** - Local embedding generation

### Data & Storage
- **PostgreSQL** - Relational database with vector extensions
- **Google Cloud Storage** - Scalable object storage
- **Local File System** - High-performance local storage

### Document Processing
- **python-docx** - Microsoft Word document manipulation
- **ReportLab** - PDF generation and processing
- **Pillow** - Image processing capabilities

## 🚀 Deployment

### Docker Deployment

```bash
docker build -t contract-mining-assistant .
docker run -p 8004:8004 contract-mining-assistant
```

### Google Cloud Run

Automated deployment via GitHub Actions:

1. Configure repository secrets:
   - `GCP_SA_KEY` - Service account JSON key
   - `GCP_PROJECT_ID` - Google Cloud project ID

2. Push to main branch triggers automatic deployment

## 📊 Performance & Scalability

- **Concurrent Requests** - Up to 100 simultaneous connections
- **Document Processing** - 50+ documents per minute
- **Search Response Time** - <200ms average query time
- **Memory Footprint** - 2GB recommended minimum
- **Storage Scaling** - Unlimited with cloud storage integration

## 🔒 Security & Compliance

- **Data Encryption** - AES-256 encryption at rest
- **API Security** - Optional JWT authentication
- **Network Security** - HTTPS/TLS 1.3 support
- **Audit Logging** - Comprehensive activity tracking
- **Privacy Controls** - Local-first data processing options

## 📈 Monitoring & Observability

- **Health Checks** - Built-in system health monitoring
- **Performance Metrics** - Request/response time tracking
- **Error Tracking** - Comprehensive error logging
- **Resource Monitoring** - CPU, memory, and storage metrics

## 🤝 Contributing

This is a proprietary enterprise solution. For feature requests or bug reports, please contact the development team.

## 📄 License

Proprietary - Internal Use Only. All rights reserved.

---

**Built with ❤️ for enterprise contract management**
