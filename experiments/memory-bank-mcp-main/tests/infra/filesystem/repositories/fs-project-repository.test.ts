import fs from "fs-extra";
import os from "os";
import path from "path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { FsProjectRepository } from "../../../../src/infra/filesystem/repositories/fs-project-repository.js";

describe("FsProjectRepository", () => {
  let tempDir: string;
  let repository: FsProjectRepository;

  beforeEach(() => {
    // Create a temporary directory for tests
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "memory-bank-test-"));
    repository = new FsProjectRepository(tempDir);
  });

  afterEach(() => {
    // Clean up after tests
    fs.removeSync(tempDir);
  });

  describe("listProjects", () => {
    it("should return an empty array when no projects exist", async () => {
      const result = await repository.listProjects();
      expect(result).toEqual([]);
    });

    it("should return project directories as Project objects", async () => {
      // Create test directories
      await fs.mkdir(path.join(tempDir, "project1"));
      await fs.mkdir(path.join(tempDir, "project2"));
      // Create a file to ensure it's not returned
      await fs.writeFile(path.join(tempDir, "not-a-project.txt"), "test");

      const result = await repository.listProjects();

      expect(result).toHaveLength(2);
      expect(result).toEqual(expect.arrayContaining(["project1", "project2"]));
    });
  });

  describe("projectExists", () => {
    it("should throw an error when project path cannot be accessed", async () => {
      // We now let errors propagate, so stat errors will throw
      const nonExistentProject = "non-existent-project";

      await expect(
        repository.projectExists(nonExistentProject)
      ).rejects.toThrow();
    });

    it("should return true when project exists", async () => {
      await fs.mkdir(path.join(tempDir, "existing-project"));

      const result = await repository.projectExists("existing-project");

      expect(result).toBe(true);
    });
  });

  describe("ensureProject", () => {
    it("should create project directory if it does not exist", async () => {
      await repository.ensureProject("new-project");

      const projectPath = path.join(tempDir, "new-project");
      const exists = await fs.pathExists(projectPath);

      expect(exists).toBe(true);
    });

    it("should not throw if project directory already exists", async () => {
      await fs.mkdir(path.join(tempDir, "existing-project"));

      await expect(
        repository.ensureProject("existing-project")
      ).resolves.not.toThrow();
    });
  });
});
