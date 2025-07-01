# Cogni Repository Dependency Audit

**Created**: 2025-01-08
**Purpose**: Complete inventory before migrating to pyproject.toml + UV management
**Status**: Research Phase - No Changes Made

## Current Dependency File Analysis

### 1. requirements.txt (74 lines)
**Location**: Root directory
**Role**: Main dependency file with comprehensive packages
**Categories Found**:
- Core dependencies (prefect, tweepy, openai, PyGithub, etc.)
- LangChain ecosystem (langchain-core, langchain-community, langchain-openai)
- LangGraph + MCP (langgraph>=0.2.79, langchain-mcp-adapters>=0.1.0)
- Testing tools (pytest, pytest-mock, pytest-asyncio, ruff, pre-commit)
- Memory & Indexing (llama-index suite, chromadb, sentence-transformers)
- API & Web (fastapi, uvicorn, gunicorn)
- AutoGen (pyautogen, autogen-core)
- Utilities (tqdm, jsonpatch, unidiff, jinja2)

### 2. services/web_api/requirements.api.txt (29 lines)
**Location**: API service directory
**Role**: API-specific dependencies
**Overlaps with requirements.txt**: fastapi, uvicorn, gunicorn, langchain packages, chromadb
**Unique additions**: onnxruntime, llama-index-embeddings-openai, llama-index-llms-openai

### 3. tests/requirements-test.txt (11 lines)
**Location**: Test directory
**Role**: Test-specific dependencies with pinned versions
**Notable**: Has specific pinned versions (pytest==7.4.0, openai==1.3.8)
**Overlaps**: pytest, chromadb, fastapi, uvicorn, httpx

### 4. services/mcp_server/pyproject.toml
**Location**: MCP server workspace member
**Role**: Already properly structured with UV
**Dependencies**: Focused on MCP server functionality
**Structure**: Uses proper dependency groups (dev)

### 5. Current main pyproject.toml
**Status**: Partially migrated
**Has**: Basic dependencies, some LangGraph packages
**Missing**: Most packages from requirements.txt
**Structure**: Uses dependency-groups for dev dependencies

## Overlap Analysis

### Major Overlaps (Same packages in multiple files):
- **Web Framework**: fastapi, uvicorn, gunicorn
- **LangChain**: langchain-core, langchain-community, langchain-openai  
- **Testing**: pytest (but different versions)
- **Memory**: chromadb
- **HTTP**: httpx
- **Utils**: tqdm

### Version Conflicts Identified:
- **pytest**: requirements.txt (>=7.0.0) vs tests/requirements-test.txt (==7.4.0)
- **openai**: requirements.txt (>=1.0.0,<1.80.0) vs tests (==1.3.8)
- **fastapi**: requirements.txt (>=0.110.0) vs tests (==0.104.1)

## UV Migration Strategy (Based on Research)

### Recommended Dependency Groups:
1. **Core runtime dependencies** → `[project.dependencies]`
2. **Development tools** → `[dependency-groups.dev]` 
3. **Testing tools** → `[dependency-groups.test]`
4. **API-specific** → `[dependency-groups.api]` or optional dependency
5. **Documentation** → `[dependency-groups.docs]` (if needed)

### UV Commands for Migration (Research Complete):
```bash
# Step 1: Import main requirements as project dependencies
uv add -r requirements.txt

# Step 2: Import dev requirements (automatically goes to [dependency-groups.dev])
uv add --dev -r tests/requirements-test.txt

# Step 3: Custom dependency groups (MANUAL - add to pyproject.toml)
# Add to pyproject.toml:
# [dependency-groups]
# api = ["onnxruntime", "llama-index-embeddings-openai", ...]
# test = ["pytest>=7.0.0", "pytest-cov", ...]

# Step 4: Install dependency groups
uv sync --group dev              # Install dev group
uv sync --group test             # Install test group  
uv sync --group api              # Install api group
uv sync --group dev --group test # Install multiple groups
uv sync                          # Install default groups (dev by default)
```

## Risk Assessment

### LOW RISK:
- Well-documented UV migration pattern
- Current pyproject.toml already partially structured
- Overlapping dependencies are manageable

### MEDIUM RISK:
- Version conflicts need resolution
- Multiple requirements files need careful consolidation
- Testing different dependency groups

### HIGH RISK:
- None identified with conservative approach

## Next Steps (READY TO EXECUTE)

### Phase 1: Import Main Dependencies (Low Risk)
1. **Execute**: `uv add -r requirements.txt` to import 74 main dependencies
2. **Verify**: Check that pyproject.toml is updated correctly
3. **Test**: Run `uv sync` to ensure installation works

### Phase 2: Import Dev Dependencies (Medium Risk - Version Conflicts)  
4. **Resolve version conflicts first** before importing test dependencies
5. **Execute**: `uv add --dev` for development tools (manual selection from tests/requirements-test.txt)
6. **Test**: Verify development environment works

### Phase 3: Create Custom Dependency Groups (Manual)
7. **Create API group**: Manually add `[dependency-groups.api]` with unique API dependencies
8. **Create test group**: Add test-specific dependencies 
9. **Test**: `uv sync --group api` and `uv sync --group test`

### Phase 4: File Cleanup
10. **Remove requirements.txt** after verifying pyproject.toml has all dependencies
11. **Remove other requirements files** 
12. **Update documentation** and setup scripts

### Phase 5: UV Lock & CI Updates
13. **Regenerate**: `uv lock` to create new lock file
14. **Update CI/Docker**: Change from pip to uv installation
15. **Test full pipeline**

## Sources
- UV documentation on dependency groups
- Research on pyproject.toml best practices
- Analysis of current workspace structure 