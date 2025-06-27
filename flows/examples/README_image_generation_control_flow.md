# Image Generation Control Flow - Cogni-Image-Generators

A sophisticated two-agent AutoGen Control Flow system for collaborative image generation using Luma and Veo2 MCP tools. This system represents the evolution from legacy "1flow, 1agent" patterns to modern Control Flow architecture with specialized collaborative agents.

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                 Image Generation Control Flow               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │  Image Creator  │    │  Image Refiner  │                │
│  │     Agent       │◄──►│     Agent       │                │
│  └─────────────────┘    └─────────────────┘                │
│          │                       │                         │
│          └───────────┬───────────┘                         │
│                      │                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              MCP Tools Integration                      │ │
│  │                                                         │ │
│  │  ┌─────────────┐    ┌─────────────┐                    │ │
│  │  │    Luma     │    │    Veo2     │                    │ │
│  │  │ MCP Server  │    │ MCP Server  │                    │ │
│  │  └─────────────┘    └─────────────┘                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Agent Specialization

#### Image Creator Agent
- **Primary Role**: Initial image generation and prompt engineering
- **Capabilities**:
  - Artistic intent analysis and interpretation
  - Optimized prompt crafting with artistic terminology
  - Tool selection and parameter optimization
  - Initial image generation execution
  - Quality assessment and refinement recommendations

#### Image Refiner Agent  
- **Primary Role**: Enhancement, modification, and iterative improvement
- **Capabilities**:
  - Image quality and composition analysis
  - Enhancement opportunity identification
  - Style transfer and artistic refinement
  - Character consistency maintenance
  - Progressive quality improvement

## Available MCP Tools

### Luma Image Generation Tools
- `GenerateImage`: Basic image generation from prompts
- `GenerateImageWithReference`: Generation guided by reference images
- `GenerateImageWithStyle`: Style-guided image generation
- `GenerateImageWithCharacter`: Character-consistent image generation
- `ModifyImage`: Targeted image modification and enhancement

### Veo2 Video Generation Tools (Future Expansion)
- `veo2_videogeneration`: Advanced video generation capabilities
- `veo2_response`: Video generation status and retrieval

## Workflow Phases

### Phase 1: Initial Image Creation
```
Creative Brief Input
        ↓
Image Creator Agent Analysis
        ↓
Prompt Engineering & Tool Selection
        ↓
Initial Image Generation
        ↓
Quality Assessment & Feedback
```

### Phase 2: Refinement Planning
```
Initial Creation Results
        ↓
Image Refiner Agent Analysis
        ↓
Enhancement Opportunity Identification
        ↓
Refinement Strategy Development
        ↓
Tool Selection & Parameter Planning
```

### Phase 3: Collaborative Enhancement
```
Refinement Plan Execution
        ↓
Targeted Modifications
        ↓
Quality Monitoring & Iteration
        ↓
Final Results Documentation
        ↓
Future Recommendations
```

## Usage Examples

### Basic Usage
```python
from flows.examples.image_generation_control_flow import image_generation_control_flow

# Default creative brief execution
result = await image_generation_control_flow()
```

### Custom Creative Brief
```python
# Custom artistic vision
custom_brief = """
A cyberpunk cityscape at night featuring:
- Neon-lit skyscrapers with holographic advertisements
- Flying cars with light trails
- Rain-soaked streets reflecting colorful lights
- Moody atmospheric lighting with purple and blue tones
- High detail, cinematic composition
"""

result = await image_generation_control_flow(custom_brief)
```

### Configuration Options
```python
# Environment variables for MCP server connections
LUMA_MCP_SSE_URL=http://localhost:8931/sse
VEO2_MCP_SSE_URL=http://localhost:8932/sse
OPENAI_API_KEY=your_openai_api_key
```

## Testing

### Test Suite Execution
```bash
# Run comprehensive tests
python flows/examples/test_image_generation_control_flow.py
```

### Test Scenarios
1. **Basic Image Generation**: Default creative brief processing
2. **Custom Creative Brief**: Complex artistic vision handling
3. **Artistic Styles**: Multiple style variations testing
4. **Workflow Phases**: End-to-end phase execution validation

## Integration with Prefect

### Flow Deployment
```bash
# Deploy to Prefect
prefect deploy --all

# Run specific deployment
prefect deployment run 'image_generation_control_flow/image-generation-control-flow'
```

### Flow Monitoring
```bash
# View flow runs
prefect flow-run ls

# Get detailed logs
prefect flow-run logs <flow-run-id>
```

## Architecture Benefits

### Compared to Legacy Patterns
- **Before**: Single agent handling all image generation tasks
- **After**: Specialized agents with clear responsibilities and collaborative workflows

### Key Advantages
1. **Specialization**: Each agent focuses on their expertise area
2. **Quality**: Iterative refinement produces superior results
3. **Scalability**: Easy to add new agents or capabilities
4. **Maintainability**: Clear separation of concerns
5. **Flexibility**: Adaptable to different creative requirements

## Technical Implementation

### Control Flow Pattern
```python
# Agent creation with specialized prompts
image_creator_agent = ProxyAgent(
    AgentId("image_creator", "image_gen_team"),
    runtime,
    tools=autogen_tools,
    system_message=image_creator_prompt,
)

image_refiner_agent = ProxyAgent(
    AgentId("image_refiner", "image_gen_team"), 
    runtime,
    tools=autogen_tools,
    system_message=image_refiner_prompt,
)
```

### MCP Integration
```python
# SSE transport for real-time communication
async with configure_existing_mcp(luma_sse_url) as (session, sdk_tools):
    # Create AutoGen adapters
    autogen_tools = [
        SseMcpToolAdapter(server_params=sse_params, tool=tool, session=session)
        for tool in sdk_tools
    ]
```

## Future Enhancements

### Planned Expansions
1. **Video Generation**: Integration with Veo2 video capabilities
2. **Multi-Modal**: Text-to-image-to-video workflows
3. **Style Libraries**: Curated style reference management
4. **Quality Metrics**: Automated assessment and scoring
5. **Asset Management**: Generated content organization and retrieval

### Integration Opportunities
- **Memory System**: Store successful prompts and parameters
- **Web Interface**: Visual creative brief submission
- **Batch Processing**: Multiple creative briefs execution
- **API Endpoints**: External system integration

## Troubleshooting

### Common Issues
1. **MCP Connection Failures**: Verify server URLs and availability
2. **Tool Access Errors**: Check MCP server deployment and permissions
3. **Agent Communication**: Validate AutoGen tool adapter configuration
4. **Memory Issues**: Monitor resource usage for large image processing

### Debug Commands
```bash
# Test MCP connectivity
curl http://localhost:8931/sse

# Verify Prefect deployment
prefect deployment ls

# Check flow logs
prefect flow-run logs --tail
```

## Performance Considerations

### Optimization Strategies
- **Tool Selection**: Choose optimal models for specific requirements
- **Parameter Tuning**: Balance quality vs generation time
- **Caching**: Reuse successful parameters and styles
- **Batch Processing**: Group similar requests for efficiency

### Resource Management
- **Memory**: Monitor image processing memory usage
- **Network**: Optimize MCP communication efficiency
- **Storage**: Manage generated image asset storage

This Control Flow system represents a significant evolution in collaborative AI workflows, providing a robust foundation for sophisticated image generation capabilities while maintaining flexibility for future enhancements. 