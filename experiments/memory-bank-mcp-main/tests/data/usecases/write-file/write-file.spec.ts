import { beforeEach, describe, expect, test, vi } from "vitest";
import { FileRepository } from "../../../../src/data/protocols/file-repository.js";
import { ProjectRepository } from "../../../../src/data/protocols/project-repository.js";
import { WriteFile } from "../../../../src/data/usecases/write-file/write-file.js";
import { WriteFileParams } from "../../../../src/domain/usecases/write-file.js";
import {
  MockFileRepository,
  MockProjectRepository,
} from "../../mocks/index.js";

describe("WriteFile UseCase", () => {
  let sut: WriteFile;
  let fileRepositoryStub: FileRepository;
  let projectRepositoryStub: ProjectRepository;

  beforeEach(() => {
    fileRepositoryStub = new MockFileRepository();
    projectRepositoryStub = new MockProjectRepository();
    sut = new WriteFile(fileRepositoryStub, projectRepositoryStub);
  });

  test("should call ProjectRepository.ensureProject with correct projectName", async () => {
    const ensureProjectSpy = vi.spyOn(projectRepositoryStub, "ensureProject");
    const params: WriteFileParams = {
      projectName: "new-project",
      fileName: "new-file.md",
      content: "New content",
    };

    vi.spyOn(fileRepositoryStub, "loadFile")
      .mockResolvedValueOnce(null) // First call checking if file exists
      .mockResolvedValueOnce("New content"); // Second call returning the saved content

    await sut.writeFile(params);

    expect(ensureProjectSpy).toHaveBeenCalledWith("new-project");
  });

  test("should check if file exists before writing", async () => {
    const loadFileSpy = vi.spyOn(fileRepositoryStub, "loadFile");
    const params: WriteFileParams = {
      projectName: "project-1",
      fileName: "new-file.md",
      content: "New content",
    };

    await sut.writeFile(params);

    expect(loadFileSpy).toHaveBeenCalledWith("project-1", "new-file.md");
  });

  test("should return null if file already exists", async () => {
    const params: WriteFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
      content: "New content",
    };

    const result = await sut.writeFile(params);

    expect(result).toBeNull();
  });

  test("should call FileRepository.writeFile with correct params if file does not exist", async () => {
    const writeFileSpy = vi.spyOn(fileRepositoryStub, "writeFile");
    const params: WriteFileParams = {
      projectName: "project-1",
      fileName: "new-file.md",
      content: "New content",
    };

    vi.spyOn(fileRepositoryStub, "loadFile")
      .mockResolvedValueOnce(null) // First call checking if file exists
      .mockResolvedValueOnce("New content"); // Second call returning the saved content

    await sut.writeFile(params);

    expect(writeFileSpy).toHaveBeenCalledWith(
      "project-1",
      "new-file.md",
      "New content"
    );
  });

  test("should return file content on successful file creation", async () => {
    const params: WriteFileParams = {
      projectName: "project-1",
      fileName: "new-file.md",
      content: "New content",
    };

    vi.spyOn(fileRepositoryStub, "loadFile")
      .mockResolvedValueOnce(null) // First call checking if file exists
      .mockResolvedValueOnce("New content"); // Second call returning the saved content

    const result = await sut.writeFile(params);

    expect(result).toBe("New content");
  });

  test("should propagate errors if repository throws", async () => {
    const error = new Error("Repository error");
    vi.spyOn(projectRepositoryStub, "ensureProject").mockRejectedValueOnce(
      error
    );
    const params: WriteFileParams = {
      projectName: "project-1",
      fileName: "new-file.md",
      content: "New content",
    };

    await expect(sut.writeFile(params)).rejects.toThrow(error);
  });
});
