#!/bin/bash

# TODO: parametrize the branch comparison (currently main..origin/cogni_graph)

# Remove previous directory if it exists and create a fresh one
rm -rf commit_diffs
mkdir -p commit_diffs

# Get all commit SHAs in reverse order (oldest first)
git fetch origin

# Store commits in a more compatible way
commit_array=()
while read -r commit; do
  commit_array+=("$commit")
done < <(git log --reverse --format="%H" main..origin/cogni_graph)

echo "Found ${#commit_array[@]} commits to process"

# Loop through the array
for commit in "${commit_array[@]}"; do
  # Get short SHA for filename
  short_sha=$(git rev-parse --short "$commit")
  
  # Create a file named after the short SHA
  output_file="commit_diffs/${short_sha}.txt"
  
  # Write SHA to file
  echo "SHA: $commit" > "$output_file"
  
  # Write commit message to file (append)
  echo -e "\nCOMMIT MESSAGE:" >> "$output_file"
  git log -1 --pretty=format:"%s" "$commit" >> "$output_file"
  
  # Write full diff to file (append)
  echo -e "\n\nDIFF:" >> "$output_file"
  git show "$commit" >> "$output_file"
  
  echo "Created $output_file"
done

echo "All commit diffs have been saved to the commit_diffs directory"
echo "Verifying file count:"
ls -l commit_diffs/ | grep -c "\.txt" 