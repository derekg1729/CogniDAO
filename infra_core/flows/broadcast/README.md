# BroadcastCogni

A system for sharing Cogni thoughts with the world through controlled human-approved broadcasts.

## MVP Features

- Human approval via LogSeq properties
- Controlled posting cadence (1-2 posts at a time)
- X (Twitter) as first broadcast channel
- Git branch for tracking changes

## Workflow

1. Human approves thoughts in LogSeq using properties
2. BroadcastCogni detects approved thoughts
3. Approved thoughts are added to a queue
4. Posts are published at controlled intervals
5. Results are tracked in LogSeq and logs

## Implementation

```
infra_core/flows/broadcast/
├── broadcast_flow.py          # Main flow implementation
├── channel_interface.py       # Common interface for channels
├── queue_manager.py           # Simple queue implementation
├── logseq_integration.py      # LogSeq query and update
├── git_integration.py         # Git branch management
├── channels/
│   └── x/
│       └── x_channel.py       # X channel implementation
└── README.md                  # This file
```

## Usage

To run the broadcast flow:

```bash
cd infra_core
python -m flows.broadcast.broadcast_flow
```

## Documentation

See the project documentation in `infra_core/docs/roadmap/`:

- [project-broadcast-cogni.md](../../docs/roadmap/project-broadcast-cogni.md) - Project overview and architecture
- [implementation-broadcast-cogni-mvp.md](../../docs/roadmap/implementation-broadcast-cogni-mvp.md) - Implementation details 