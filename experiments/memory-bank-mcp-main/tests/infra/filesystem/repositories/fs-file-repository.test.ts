import fs from "fs-extra";
import os from "os";
import path from "path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { FsFileRepository } from "../../../../src/infra/filesystem/repositories/fs-file-repository.js";

describe("FsFileRepository", () => {
  let tempDir: string;
  let repository: FsFileRepository;
  const projectName = "test-project";
  const fileName = "test.md";
  const fileContent = "Test content";

  beforeEach(async () => {
    // Create a temporary directory for tests
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memory-bank-test-"));
    repository = new FsFileRepository(tempDir);

    // Create a test project directory
    await fs.mkdir(path.join(tempDir, projectName));
  });

  afterEach(() => {
    // Clean up after tests
    fs.removeSync(tempDir);
  });

  describe("listFiles", () => {
    it("should return an empty array for a project that doesn't exist", async () => {
      const result = await repository.listFiles("non-existent-project");
      expect(result).toEqual([]);
    });

    it("should return an empty array when no files exist in the project", async () => {
      const result = await repository.listFiles(projectName);
      expect(result).toEqual([]);
    });

    it("should return file names within the project directory", async () => {
      // Create test files
      await fs.writeFile(path.join(tempDir, projectName, "file1.md"), "test");
      await fs.writeFile(path.join(tempDir, projectName, "file2.txt"), "test");
      // Create a directory to ensure it's not returned
      await fs.mkdir(path.join(tempDir, projectName, "not-a-file"));

      const result = await repository.listFiles(projectName);

      expect(result).toHaveLength(2);
      expect(result).toEqual(expect.arrayContaining(["file1.md", "file2.txt"]));
    });
  });

  describe("loadFile", () => {
    it("should return null when the file doesn't exist", async () => {
      const result = await repository.loadFile(projectName, "non-existent.md");
      expect(result).toBeNull();
    });

    it("should return null when the project doesn't exist", async () => {
      const result = await repository.loadFile(
        "non-existent-project",
        fileName
      );
      expect(result).toBeNull();
    });

    it("should return the file content when the file exists", async () => {
      // Create a test file
      await fs.writeFile(
        path.join(tempDir, projectName, fileName),
        fileContent
      );

      const result = await repository.loadFile(projectName, fileName);

      expect(result).toBe(fileContent);
    });
  });

  describe("writeFile", () => {
    it("should create the project directory if it doesn't exist", async () => {
      const newProjectName = "new-project";
      const newFilePath = path.join(tempDir, newProjectName, fileName);

      await repository.writeFile(newProjectName, fileName, fileContent);

      const exists = await fs.pathExists(newFilePath);
      expect(exists).toBe(true);
    });

    it("should write file content to the specified file", async () => {
      await repository.writeFile(projectName, fileName, fileContent);

      const content = await fs.readFile(
        path.join(tempDir, projectName, fileName),
        "utf-8"
      );
      expect(content).toBe(fileContent);
    });

    it("should return the file content after writing", async () => {
      const result = await repository.writeFile(
        projectName,
        fileName,
        fileContent
      );

      expect(result).toBe(fileContent);
    });

    it("should return null if the file already exists", async () => {
      // Create a test file first
      await fs.writeFile(
        path.join(tempDir, projectName, fileName),
        "Original content"
      );

      const result = await repository.writeFile(
        projectName,
        fileName,
        fileContent
      );

      expect(result).toBeNull();

      // Verify content wasn't changed
      const content = await fs.readFile(
        path.join(tempDir, projectName, fileName),
        "utf-8"
      );
      expect(content).toBe("Original content");
    });
  });

  describe("updateFile", () => {
    it("should return null when the file doesn't exist", async () => {
      const result = await repository.updateFile(
        projectName,
        "non-existent.md",
        fileContent
      );
      expect(result).toBeNull();
    });

    it("should return null when the project doesn't exist", async () => {
      const result = await repository.updateFile(
        "non-existent-project",
        fileName,
        fileContent
      );
      expect(result).toBeNull();
    });

    it("should update file content for an existing file", async () => {
      // Create a test file first
      await fs.writeFile(
        path.join(tempDir, projectName, fileName),
        "Original content"
      );

      const updatedContent = "Updated content";
      const result = await repository.updateFile(
        projectName,
        fileName,
        updatedContent
      );

      expect(result).toBe(updatedContent);

      // Verify content was changed
      const content = await fs.readFile(
        path.join(tempDir, projectName, fileName),
        "utf-8"
      );
      expect(content).toBe(updatedContent);
    });

    it("should return the updated file content", async () => {
      // Create a test file first
      await fs.writeFile(
        path.join(tempDir, projectName, fileName),
        "Original content"
      );

      const updatedContent = "Updated content";
      const result = await repository.updateFile(
        projectName,
        fileName,
        updatedContent
      );

      expect(result).toBe(updatedContent);
    });
  });
});
