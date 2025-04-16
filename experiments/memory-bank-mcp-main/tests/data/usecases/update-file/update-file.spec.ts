import { beforeEach, describe, expect, test, vi } from "vitest";
import { FileRepository } from "../../../../src/data/protocols/file-repository.js";
import { ProjectRepository } from "../../../../src/data/protocols/project-repository.js";
import { UpdateFile } from "../../../../src/data/usecases/update-file/update-file.js";
import { UpdateFileParams } from "../../../../src/domain/usecases/update-file.js";
import {
  MockFileRepository,
  MockProjectRepository,
} from "../../mocks/index.js";

describe("UpdateFile UseCase", () => {
  let sut: UpdateFile;
  let fileRepositoryStub: FileRepository;
  let projectRepositoryStub: ProjectRepository;

  beforeEach(() => {
    fileRepositoryStub = new MockFileRepository();
    projectRepositoryStub = new MockProjectRepository();
    sut = new UpdateFile(fileRepositoryStub, projectRepositoryStub);
  });

  test("should call ProjectRepository.projectExists with correct projectName", async () => {
    const projectExistsSpy = vi.spyOn(projectRepositoryStub, "projectExists");
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "Updated content",
    };

    await sut.updateFile(params);

    expect(projectExistsSpy).toHaveBeenCalledWith("project-1");
  });

  test("should return null if project does not exist", async () => {
    vi.spyOn(projectRepositoryStub, "projectExists").mockResolvedValueOnce(
      false
    );
    const params: UpdateFileParams = {
      projectName: "non-existent-project",
      fileName: "file1.md",
      content: "Updated content",
    };

    const result = await sut.updateFile(params);

    expect(result).toBeNull();
  });

  test("should check if file exists before updating", async () => {
    const loadFileSpy = vi.spyOn(fileRepositoryStub, "loadFile");
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "Updated content",
    };

    await sut.updateFile(params);

    expect(loadFileSpy).toHaveBeenCalledWith("project-1", "file1.md");
  });

  test("should return null if file does not exist", async () => {
    vi.spyOn(fileRepositoryStub, "loadFile").mockResolvedValueOnce(null);
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "non-existent-file.md",
      content: "Updated content",
    };

    const result = await sut.updateFile(params);

    expect(result).toBeNull();
  });

  test("should call FileRepository.updateFile with correct params if file exists", async () => {
    const updateFileSpy = vi.spyOn(fileRepositoryStub, "updateFile");
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "Updated content",
    };

    await sut.updateFile(params);

    expect(updateFileSpy).toHaveBeenCalledWith(
      "project-1",
      "file1.md",
      "Updated content"
    );
  });

  test("should return file content on successful file update", async () => {
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "Updated content",
    };

    const result = await sut.updateFile(params);

    expect(result).toBe("Updated content");
  });

  test("should propagate errors if repository throws", async () => {
    const error = new Error("Repository error");
    vi.spyOn(projectRepositoryStub, "projectExists").mockRejectedValueOnce(
      error
    );
    const params: UpdateFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "Updated content",
    };

    await expect(sut.updateFile(params)).rejects.toThrow(error);
  });
});
