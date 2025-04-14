import { FileRepository } from "../../../src/data/protocols/file-repository.js";

export class MockFileRepository implements FileRepository {
  private projectFiles: Record<string, Record<string, string>> = {
    "project-1": {
      "file1.md": "Content of file1.md",
      "file2.md": "Content of file2.md",
    },
    "project-2": {
      "fileA.md": "Content of fileA.md",
      "fileB.md": "Content of fileB.md",
    },
  };

  async listFiles(projectName: string): Promise<string[]> {
    return Object.keys(this.projectFiles[projectName] || {});
  }

  async loadFile(
    projectName: string,
    fileName: string
  ): Promise<string | null> {
    if (
      this.projectFiles[projectName] &&
      this.projectFiles[projectName][fileName]
    ) {
      return this.projectFiles[projectName][fileName];
    }
    return null;
  }

  async writeFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<string | null> {
    if (!this.projectFiles[projectName]) {
      this.projectFiles[projectName] = {};
    }
    this.projectFiles[projectName][fileName] = content;
    return content;
  }

  async updateFile(
    projectName: string,
    fileName: string,
    content: string
  ): Promise<string | null> {
    if (
      this.projectFiles[projectName] &&
      this.projectFiles[projectName][fileName]
    ) {
      this.projectFiles[projectName][fileName] = content;
      return content;
    }
    return null;
  }
}
