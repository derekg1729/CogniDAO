import { beforeEach, describe, expect, test, vi } from "vitest";
import { FileRepository } from "../../../../src/data/protocols/file-repository.js";
import { ProjectRepository } from "../../../../src/data/protocols/project-repository.js";
import { ListProjectFiles } from "../../../../src/data/usecases/list-project-files/list-project-files.js";
import { ListProjectFilesParams } from "../../../../src/domain/usecases/list-project-files.js";
import {
  MockFileRepository,
  MockProjectRepository,
} from "../../mocks/index.js";

describe("ListProjectFiles UseCase", () => {
  let sut: ListProjectFiles;
  let fileRepositoryStub: FileRepository;
  let projectRepositoryStub: ProjectRepository;

  beforeEach(() => {
    fileRepositoryStub = new MockFileRepository();
    projectRepositoryStub = new MockProjectRepository();
    sut = new ListProjectFiles(fileRepositoryStub, projectRepositoryStub);
  });

  test("should call ProjectRepository.projectExists with correct projectName", async () => {
    const projectExistsSpy = vi.spyOn(projectRepositoryStub, "projectExists");
    const params: ListProjectFilesParams = { projectName: "project-1" };

    await sut.listProjectFiles(params);

    expect(projectExistsSpy).toHaveBeenCalledWith("project-1");
  });

  test("should return empty array if project does not exist", async () => {
    vi.spyOn(projectRepositoryStub, "projectExists").mockResolvedValueOnce(
      false
    );
    const params: ListProjectFilesParams = {
      projectName: "non-existent-project",
    };

    const result = await sut.listProjectFiles(params);

    expect(result).toEqual([]);
  });

  test("should call FileRepository.listFiles with correct projectName if project exists", async () => {
    vi.spyOn(projectRepositoryStub, "projectExists").mockResolvedValueOnce(
      true
    );
    const listFilesSpy = vi.spyOn(fileRepositoryStub, "listFiles");
    const params: ListProjectFilesParams = { projectName: "project-1" };

    await sut.listProjectFiles(params);

    expect(listFilesSpy).toHaveBeenCalledWith("project-1");
  });

  test("should return files list on success", async () => {
    const params: ListProjectFilesParams = { projectName: "project-1" };

    const files = await sut.listProjectFiles(params);

    expect(files).toEqual(["file1.md", "file2.md"]);
  });

  test("should propagate errors if repository throws", async () => {
    const error = new Error("Repository error");
    vi.spyOn(projectRepositoryStub, "projectExists").mockRejectedValueOnce(
      error
    );
    const params: ListProjectFilesParams = { projectName: "project-1" };

    await expect(sut.listProjectFiles(params)).rejects.toThrow(error);
  });
});
