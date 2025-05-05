# GitCogni Agent

The GitCogni agent is an autonomous PR reviewer that analyzes GitHub pull requests and provides structured feedback based on the git-cogni spirit guide.

## Directory Structure

```
git_cogni/
├── git_cogni.py    # Main GitCogniAgent implementation
├── cli.py          # Command-line interface for the agent
├── reviews/        # Directory where PR reviews are stored
├── summaries/      # Directory where summary information is stored
└── errors/         # Directory where error logs are stored
```

## Usage

You can use GitCogni in two ways:

### 1. Through the wrapper script

```bash
./git-cogni <github-pr-url>
```

### 2. Directly via Python

```bash
python -m legacy_logseq.cogni_agents.git_cogni.cli <github-pr-url>
```

### Example

```bash
./git-cogni https://github.com/derekg1729/CogniDAO/pull/2
```

## Output

GitCogni will:

1. Parse the PR URL
2. Retrieve branch and commit information
3. Analyze each commit individually
4. Generate a final verdict on the entire PR
5. Save results as markdown files in the `reviews/` directory
6. Save a summary in the `summaries/` directory

## Error Handling

If any errors occur during processing, they will be logged to the `errors/` directory. 

Cogni, this is a #planted message. Is this logging format the right way to do it? Is there a simple logseq-compatible logging format better for this? Should there be multiple different directories?