import { beforeEach, describe, expect, test, vi } from "vitest";
import { ProjectRepository } from "../../../../src/data/protocols/project-repository.js";
import { ListProjects } from "../../../../src/data/usecases/list-projects/list-projects.js";
import { MockProjectRepository } from "../../mocks/index.js";

describe("ListProjects UseCase", () => {
  let sut: ListProjects;
  let projectRepositoryStub: ProjectRepository;

  beforeEach(() => {
    projectRepositoryStub = new MockProjectRepository();
    sut = new ListProjects(projectRepositoryStub);
  });

  test("should call ProjectRepository.listProjects()", async () => {
    const listProjectsSpy = vi.spyOn(projectRepositoryStub, "listProjects");

    await sut.listProjects();

    expect(listProjectsSpy).toHaveBeenCalledTimes(1);
  });

  test("should return a list of projects on success", async () => {
    const projects = await sut.listProjects();

    expect(projects).toEqual(["project-1", "project-2"]);
  });

  test("should propagate errors if repository throws", async () => {
    const error = new Error("Repository error");
    vi.spyOn(projectRepositoryStub, "listProjects").mockRejectedValueOnce(
      error
    );

    await expect(sut.listProjects()).rejects.toThrow(error);
  });
});
