import { beforeEach, describe, expect, test, vi } from "vitest";
import { FileRepository } from "../../../../src/data/protocols/file-repository.js";
import { ProjectRepository } from "../../../../src/data/protocols/project-repository.js";
import { ReadFile } from "../../../../src/data/usecases/read-file/read-file.js";
import { ReadFileParams } from "../../../../src/domain/usecases/read-file.js";
import {
  MockFileRepository,
  MockProjectRepository,
} from "../../mocks/index.js";

describe("ReadFile UseCase", () => {
  let sut: ReadFile;
  let fileRepositoryStub: FileRepository;
  let projectRepositoryStub: ProjectRepository;

  beforeEach(() => {
    fileRepositoryStub = new MockFileRepository();
    projectRepositoryStub = new MockProjectRepository();
    sut = new ReadFile(fileRepositoryStub, projectRepositoryStub);
  });

  test("should call ProjectRepository.projectExists with correct projectName", async () => {
    const projectExistsSpy = vi.spyOn(projectRepositoryStub, "projectExists");
    const params: ReadFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
    };

    await sut.readFile(params);

    expect(projectExistsSpy).toHaveBeenCalledWith("project-1");
  });

  test("should return null if project does not exist", async () => {
    vi.spyOn(projectRepositoryStub, "projectExists").mockResolvedValueOnce(
      false
    );
    const params: ReadFileParams = {
      projectName: "non-existent-project",
      fileName: "file1.md",
    };

    const result = await sut.readFile(params);

    expect(result).toBeNull();
  });

  test("should call FileRepository.loadFile with correct params if project exists", async () => {
    const loadFileSpy = vi.spyOn(fileRepositoryStub, "loadFile");
    const params: ReadFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
    };

    await sut.readFile(params);

    expect(loadFileSpy).toHaveBeenCalledWith("project-1", "file1.md");
  });

  test("should return file content on success", async () => {
    const params: ReadFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
    };

    const content = await sut.readFile(params);

    expect(content).toBe("Content of file1.md");
  });

  test("should return null if file does not exist", async () => {
    vi.spyOn(fileRepositoryStub, "loadFile").mockResolvedValueOnce(null);
    const params: ReadFileParams = {
      projectName: "project-1",
      fileName: "non-existent-file.md",
    };

    const content = await sut.readFile(params);

    expect(content).toBeNull();
  });

  test("should propagate errors if repository throws", async () => {
    const error = new Error("Repository error");
    vi.spyOn(projectRepositoryStub, "projectExists").mockRejectedValueOnce(
      error
    );
    const params: ReadFileParams = {
      projectName: "project-1",
      fileName: "file1.md",
    };

    await expect(sut.readFile(params)).rejects.toThrow(error);
  });
});
